-- get_available_slots: returns up to 5 bookable start times for a service on a date.
--
-- time-of-day filter (#3): optional p_from_time / p_to_time (HH:MM text) restrict the
-- result to slots whose start time falls within [from, to]. When both are NULL the
-- behaviour is unchanged (the 5 earliest slots of the day). With a window, it returns
-- the 5 earliest slots INSIDE that window — so "entre las 9 y las 11" / "por la tarde"
-- no longer get answered with the earliest-of-the-day morning slots.
--
-- The old 2-arg signature is dropped so PostgREST resolves to this one unambiguously;
-- callers that omit the window simply don't send p_from_time / p_to_time (they default
-- to NULL).
DROP FUNCTION IF EXISTS public.get_available_slots(text, date);

CREATE OR REPLACE FUNCTION public.get_available_slots(
    p_service_name text,
    p_date date,
    p_from_time text DEFAULT NULL,
    p_to_time text DEFAULT NULL
)
 RETURNS TABLE(doctor_id integer, doctor_name text, slot_time text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
    v_service_id INT; v_duration INT; v_day TEXT;
BEGIN
    IF p_date < CURRENT_DATE THEN RETURN; END IF;

    SELECT id, duration_min INTO v_service_id, v_duration FROM services WHERE name = p_service_name;
    IF v_service_id IS NULL THEN RETURN; END IF;

    v_day := (ARRAY['monday','tuesday','wednesday','thursday','friday','saturday','sunday'])[EXTRACT(ISODOW FROM p_date)::int];

    RETURN QUERY
    WITH doctors_filtered AS (
        SELECT d.id, d.name FROM doctors d
        JOIN doctor_services ds ON d.id = ds.doctor_id
        WHERE ds.service_id = v_service_id AND d.active = TRUE
    ),
    working AS (
        SELECT df.id AS doctor_id, df.name AS doctor_name, (p_date + wh.start_time) AS start_dt, (p_date + wh.end_time) AS end_dt
        FROM doctors_filtered df JOIN working_hours wh ON wh.doctor_id = df.id
        WHERE LOWER(wh.day_of_week) = v_day
    ),
    exceptions_applied AS (
        SELECT w.doctor_id, w.doctor_name,
            CASE WHEN e.type = 'partial' THEN GREATEST(w.start_dt, p_date + e.start_time) ELSE w.start_dt END AS start_dt,
            CASE WHEN e.type = 'partial' THEN LEAST(w.end_dt, p_date + e.end_time) ELSE w.end_dt END AS end_dt,
            e.type
        FROM working w LEFT JOIN exceptions e ON e.doctor_id = w.doctor_id AND e.date = p_date
    ),
    valid_days AS (SELECT * FROM exceptions_applied WHERE type IS NULL OR type <> 'vacation'),
    generated_slots AS (
        SELECT vd.doctor_id, vd.doctor_name,
            generate_series(vd.start_dt, vd.end_dt - (v_duration || ' minutes')::interval, '15 minutes'::interval) AS slot_start
        FROM valid_days vd
    ),
    filtered_slots AS (
        SELECT gs.* FROM generated_slots gs
        WHERE NOT EXISTS (
            SELECT 1 FROM appointments a
            WHERE a.doctor_id = gs.doctor_id AND a.date = p_date AND a.status = 'active'
              AND NOT (gs.slot_start + (v_duration || ' minutes')::interval <= (p_date + a.start_time) OR gs.slot_start >= (p_date + a.end_time))
        )
    )
    SELECT fs.doctor_id, fs.doctor_name, TO_CHAR(fs.slot_start, 'HH24:MI') AS slot_time
    FROM filtered_slots fs
    WHERE (p_from_time IS NULL OR fs.slot_start::time >= p_from_time::time)
      AND (p_to_time   IS NULL OR fs.slot_start::time <= p_to_time::time)
    ORDER BY fs.slot_start LIMIT 5;
END;
$function$;
