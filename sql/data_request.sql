SELECT  d.deviceid, count(s)
FROM  device d
LEFT JOIN search s  ON  s.deviceid = d.deviceid
LEFT JOIN  dmasuser du  ON  du.dmasuserid = s.dmasuserid
LEFT JOIN  dmasgroupuser dgu ON  (
dgu.dmasuserid = du.dmasuserid
AND dgu.dmasgroupid =8
)
WHERE  d.devicetypeid=176
AND dgu.dmasgroupid IS NULL
AND (
SELECT sitedeviceid
FROM  sitedevice
WHERE  deviceid=d.deviceid
AND siteid NOT IN (SELECT siteid FROM site WHERE locationid IN (20,98,99))
LIMIT 1
) IS NOT NULL
GROUP BY d.deviceid
