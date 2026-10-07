-- Adapted from postgresql-audit 0.18.0 (https://github.com/kvesteri/postgresql-audit);
-- see LICENSE.postgresql-audit in this directory. Rendered by `spellbot.audit.render_sql`.

CREATE OR REPLACE FUNCTION jsonb_change_key_name(data jsonb, old_key text, new_key text)
RETURNS jsonb
IMMUTABLE
LANGUAGE sql
AS $$
    SELECT ('{'||string_agg(to_json(CASE WHEN key = old_key THEN new_key ELSE key END)||':'||value, ',')||'}')::jsonb
    FROM (
        SELECT *
        FROM jsonb_each(data)
    ) t;
$$;
