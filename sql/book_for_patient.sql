-- book_for_patient: core booking routine shared by book_appointment_safe and
-- reschedule_appointment_safe. It already validates working hours, vacation/partial
-- exceptions, the one-active-appointment policy, AND slot conflicts (with FOR UPDATE
-- SKIP LOCKED for concurrency).
--
-- slot-validation change: also reject any start time that is NOT on the 15-minute
-- grid that get_available_slots offers (all working hours start on the hour, so the
-- grid is :00/:15/:30/:45). Together with the existing conflict/hours checks this
-- means the RPC accepts ONLY times get_available_slots would actually present —
-- a hallucinated/off-grid time (e.g. 09:07) is refused instead of booked.
CREATE OR REPLACE FUNCTION public.book_for_patient(p_service_name text, p_date date, p_time text, p_patient_id integer)
 RETURNS TABLE(success boolean, message text, appointment_id integer, doctor_id integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
    v_service_id INT; v_duration INT; v_doctor_id INT;
    v_start_time TIME; v_end_time TIME; v_appointment_id INT; v_day TEXT;
BEGIN
    IF p_date < CURRENT_DATE THEN
        RETURN QUERY SELECT FALSE, 'Cannot book a date in the past'::TEXT, NULL::INT, NULL::INT; RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM patients WHERE id = p_patient_id) THEN
        RETURN QUERY SELECT FALSE, 'Invalid patient'::TEXT, NULL::INT, NULL::INT; RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM appointments WHERE patient_id = p_patient_id AND status = 'active') THEN
        RETURN QUERY SELECT FALSE, 'Patient already has an active appointment'::TEXT, NULL::INT, NULL::INT; RETURN;
    END IF;

    SELECT id, duration_min INTO v_service_id, v_duration FROM services WHERE name = p_service_name;
    IF v_service_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'Invalid service'::TEXT, NULL::INT, NULL::INT; RETURN;
    END IF;

    v_start_time := p_time::TIME;

    -- Reject times that are not on the 15-minute slot grid get_available_slots offers
    -- (working hours all start on the hour). Blocks off-grid invented times like 09:07.
    IF EXTRACT(SECOND FROM v_start_time) <> 0
       OR (EXTRACT(MINUTE FROM v_start_time)::int % 15) <> 0 THEN
        RETURN QUERY SELECT FALSE, 'Requested time is not an available slot'::TEXT, NULL::INT, NULL::INT; RETURN;
    END IF;

    v_end_time := v_start_time + (v_duration || ' minutes')::interval;
    v_day := (ARRAY['monday','tuesday','wednesday','thursday','friday','saturday','sunday'])[EXTRACT(ISODOW FROM p_date)::int];

    WITH eligible AS (
        SELECT d.id, COUNT(a.id) AS active_load
        FROM doctors d
        JOIN doctor_services ds ON d.id = ds.doctor_id
        JOIN working_hours wh ON wh.doctor_id = d.id AND LOWER(wh.day_of_week) = v_day
        LEFT JOIN appointments a ON a.doctor_id = d.id AND a.date = p_date AND a.status = 'active'
        WHERE ds.service_id = v_service_id
          AND d.active = TRUE
          AND v_start_time >= wh.start_time
          AND v_end_time <= wh.end_time
          AND NOT EXISTS (SELECT 1 FROM exceptions ex WHERE ex.doctor_id = d.id AND ex.date = p_date AND ex.type = 'vacation')
          AND (
              NOT EXISTS (SELECT 1 FROM exceptions ex WHERE ex.doctor_id = d.id AND ex.date = p_date AND ex.type = 'partial')
              OR EXISTS (SELECT 1 FROM exceptions ex WHERE ex.doctor_id = d.id AND ex.date = p_date AND ex.type = 'partial' AND v_start_time >= ex.start_time AND v_end_time <= ex.end_time)
          )
          AND NOT EXISTS (
              SELECT 1 FROM appointments a2
              WHERE a2.doctor_id = d.id AND a2.date = p_date AND a2.status = 'active'
                AND NOT (v_end_time <= a2.start_time OR v_start_time >= a2.end_time)
          )
        GROUP BY d.id
    )
    SELECT d.id INTO v_doctor_id
    FROM doctors d JOIN eligible e ON e.id = d.id
    ORDER BY e.active_load ASC LIMIT 1 FOR UPDATE OF d SKIP LOCKED;

    IF v_doctor_id IS NULL THEN
        RETURN QUERY SELECT FALSE, 'No available doctor'::TEXT, NULL::INT, NULL::INT; RETURN;
    END IF;

    INSERT INTO appointments (doctor_id, service_id, patient_id, date, start_time, end_time, status)
    VALUES (v_doctor_id, v_service_id, p_patient_id, p_date, v_start_time, v_end_time, 'active')
    RETURNING id INTO v_appointment_id;

    RETURN QUERY SELECT TRUE, 'Booked'::TEXT, v_appointment_id, v_doctor_id;
END;
$function$;
