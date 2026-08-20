CREATE OR REPLACE VIEW gold.vw_customer_overview AS
SELECT c."customerId", c."profileId", c."name", c."number", c."number2",
       c.gender, c."dateOfBirth", c."accountType", c.branch,
       COUNT(co."customerId") AS "totalComplaints",
       MIN(co."logDate") AS "firstComplaintDate",
       MAX(co."logDate") AS "lastComplaintDate"
FROM gold.customers c
LEFT JOIN gold.complaints co ON c."customerId" = co."customerId"
GROUP BY c."customerId", c."profileId", c."name", c."number", c."number2",
         c.gender, c."dateOfBirth", c."accountType", c.branch;

CREATE OR REPLACE VIEW gold.vw_complaint_summary AS
SELECT co."customerId", c."name", c."number", co."profileId",
       co."logDate", co."complaintSource", co."natureOfComplaint",
       co."subject", co."detailsOfComplaint", co."status",
       co."resolutionDate", co."turnaroundTime", co."location",
       co."region", co."updates", co."comment", co."reasonForReversalRequest",
       CASE
           WHEN co."turnaroundTime" <= 24 THEN 'Within 1 day'
           WHEN co."turnaroundTime" <= 72 THEN 'Within 3 days'
           ELSE 'Over 3 days'
       END AS "turnaroundCategory"
FROM gold.complaints co
JOIN gold.customers c ON co."customerId" = c."customerId";

CREATE OR REPLACE VIEW gold.vw_regional_stats AS
SELECT region,
       COUNT(*) AS "totalComplaints",
       COUNT(DISTINCT "customerId") AS "uniqueCustomers",
       AVG("turnaroundTime") AS "avgTurnaroundTime",
       SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS "resolvedCount",
       ROUND((SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 2) AS "resolutionRate"
FROM gold.complaints
WHERE region IS NOT NULL AND region != 'Unknown'
GROUP BY region
ORDER BY "totalComplaints" DESC;

CREATE OR REPLACE VIEW gold.vw_complaint_status AS
SELECT co."status",
       COUNT(*) AS "complaintCount",
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM gold.complaints), 2) AS "percentage",
       AVG(co."turnaroundTime") AS "avgTurnaroundTime",
       MIN(co."logDate") AS "oldestComplaint",
       MAX(co."logDate") AS "newestComplaint"
FROM gold.complaints co
GROUP BY co."status"
ORDER BY "complaintCount" DESC;

CREATE OR REPLACE VIEW gold.vw_monthly_trends AS
SELECT TO_CHAR(DATE_TRUNC('month', co."logDate"), 'Month YYYY') AS "month",
       COUNT(*) AS "totalComplaints",
       COUNT(DISTINCT co."customerId") AS "uniqueCustomers",
       AVG(co."turnaroundTime") AS "avgTurnaroundTime",
       MODE() WITHIN GROUP (ORDER BY co."natureOfComplaint") AS "topComplaintType",
       MODE() WITHIN GROUP (ORDER BY co."region") AS "topRegion"
FROM gold.complaints co
WHERE co."logDate" IS NOT NULL
GROUP BY DATE_TRUNC('month', co."logDate")
ORDER BY DATE_TRUNC('month', co."logDate") DESC;