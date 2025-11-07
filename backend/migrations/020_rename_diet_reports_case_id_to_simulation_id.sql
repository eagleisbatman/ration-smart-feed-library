-- Rename column case_id to simulation_id in diet_reports
ALTER TABLE diet_reports RENAME COLUMN case_id TO simulation_id;

-- Drop old index if exists and recreate with new name (safe guards)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'idx_diet_reports_case_id'
    ) THEN
        EXECUTE 'DROP INDEX idx_diet_reports_case_id';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_diet_reports_simulation_id ON diet_reports(simulation_id);

-- Update comments
COMMENT ON COLUMN diet_reports.simulation_id IS 'Simulation identifier (previously case_id)';

