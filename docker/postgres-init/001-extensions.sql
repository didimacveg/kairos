-- Extensiones requeridas por KAIROS. Se ejecuta una sola vez, al crear el
-- volumen de datos. Si añades extensiones despues, hazlo por migracion.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
