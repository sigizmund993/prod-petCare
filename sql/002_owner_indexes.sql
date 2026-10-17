CREATE INDEX IF NOT EXISTS pets_own_ids_idx ON pets USING GIN (own_ids);
CREATE INDEX IF NOT EXISTS pets_prop_ids_idx ON pets USING GIN (prop_ids);
CREATE INDEX IF NOT EXISTS props_own_ids_idx ON props USING GIN (own_ids);
