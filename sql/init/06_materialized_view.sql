CREATE MATERIALIZED VIEW IF NOT EXISTS gold.mv_monthly_complaint_summary AS
SELECT TO_CHAR(DATE_TRUNC('month', co."logDate"), 'Month YYYY') AS "month",
       COUNT(*) AS "totalComplaints",
       COUNT(DISTINCT co."customerId") AS "uniqueCustomers",
       AVG(co."turnaroundTime") AS "avgTurnaroundTime"
FROM gold.complaints co
WHERE co."logDate" IS NOT NULL
GROUP BY DATE_TRUNC('month', co."logDate")
ORDER BY DATE_TRUNC('month', co."logDate") DESC;