WITH RECURSIVE topology_device(deviceid, devicecode, devicecategoryid, deviceportid) AS (
SELECT d.deviceid, d.devicecode, d.devicecategoryid, dp1.deviceportid
FROM device d
JOIN deviceport dp2 ON dp2.deviceid = d.deviceid
JOIN topology t1 ON t1.deviceportid2 = dp2.deviceportid
JOIN deviceport dp1 ON dp1.deviceportid = t1.deviceportid1
WHERE d.deviceid = %s
UNION
SELECT d.deviceid, d.devicecode, d.devicecategoryid, dp1.deviceportid
FROM topology_device td
JOIN deviceport dp2 ON dp2.deviceid = td.deviceid
JOIN topology t1 ON t1.deviceportid2 = dp2.deviceportid
JOIN deviceport dp1 ON dp1.deviceportid = t1.deviceportid1
JOIN device d ON d.deviceid = dp1.deviceid
WHERE t1.dateto IS NULL
)
SELECT td.deviceid, td.devicecode, sc.sensorcode
FROM topology_device td
JOIN sensor s ON s.deviceportid = td.deviceportid
JOIN sensorcode sc ON sc.sensorcodeid = s.sensorcodeid
WHERE td.devicecategoryid = 38
AND sc.sensorcode LIKE '%%_voltagevalue';
