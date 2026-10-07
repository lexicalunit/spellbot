-- Adapted from postgresql-audit 0.18.0 (https://github.com/kvesteri/postgresql-audit);
-- see LICENSE.postgresql-audit in this directory. Rendered by `spellbot.audit.render_sql`.

CREATE SCHEMA ${schema};
REVOKE ALL ON SCHEMA ${schema} FROM public;
