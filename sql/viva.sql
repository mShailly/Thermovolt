-- PostgreSQL examples, after saving at least one experiment.
SELECT * FROM experiment_followups;
SELECT e.name,m.title,m.status FROM experiments e JOIN maintenance m ON e.id=m.experiment_id;
SELECT status,COUNT(*) FROM maintenance GROUP BY status HAVING COUNT(*)>=1;
SELECT name FROM experiments WHERE id IN (SELECT experiment_id FROM maintenance WHERE status='open');
EXPLAIN ANALYZE SELECT * FROM maintenance WHERE experiment_id='replace-with-a-real-id';
-- Atomicity: a rolled-back insert does not remain in the database.
BEGIN;
INSERT INTO experiments VALUES('rollback-demo','Rollback demonstration','{}','{}',CURRENT_TIMESTAMP::text);
ROLLBACK;
SELECT COUNT(*) FROM experiments WHERE id='rollback-demo';
-- With a teacher-approved demo role already created by the database owner:
-- GRANT SELECT ON experiments,maintenance TO demo_reader;
-- REVOKE SELECT ON experiments,maintenance FROM demo_reader;
