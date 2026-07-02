WITH RECURSIVE bi_topology AS (
    -- Step 1: Flatten and double-map the active wire lines into a fast bidirectional view
    SELECT deviceportid1 AS local_portid, deviceportid2 AS parent_portid FROM topology WHERE dateto IS NULL
    UNION ALL
    SELECT deviceportid2 AS local_portid, deviceportid1 AS parent_portid FROM topology WHERE dateto IS NULL
),
topology_tree AS (
    -- Base Case: Start with the target instrument device record
    SELECT 
        d.deviceid,
        d.devicecode,
        d.devicecategoryid,
        NULL::integer as port_id,
        NULL::varchar as sensorcode,
        1 as hop_level,
        ARRAY[d.deviceid] as visited_ids
    FROM device d
    WHERE d.deviceid = %s
    
    UNION ALL
    
    -- Recursive Case: Move up the chain using our bidirectional mapping table
    SELECT 
        d_parent.deviceid,
        d_parent.devicecode,
        d_parent.devicecategoryid,
        bit.parent_portid as port_id,
        sc.sensorcode,
        tt.hop_level + 1,
        tt.visited_ids || d_parent.deviceid
    FROM topology_tree tt
    -- Join to the current milestone's available ports
    JOIN deviceport dp_curr ON dp_curr.deviceid = tt.deviceid
    -- Use our single-reference bidirectional table mapping
    JOIN bi_topology bit ON bit.local_portid = dp_curr.deviceportid
    -- Find the neighbor device information on the other end
    JOIN deviceport dp_parent ON dp_parent.deviceportid = bit.parent_portid
    JOIN device d_parent ON d_parent.deviceid = dp_parent.deviceid
    -- Fetch power tracking channels if assigned
    LEFT JOIN sensor s ON s.deviceportid = bit.parent_portid
    LEFT JOIN sensorcode sc ON sc.sensorcodeid = s.sensorcodeid
    WHERE NOT (d_parent.deviceid = ANY(tt.visited_ids))
      -- 🛑 THE UNIVERSAL CEILING: Stop immediately if the milestone we are leaving is a Junction Box (Cat 38)
      AND tt.devicecategoryid <> 38
)
SELECT DISTINCT 
    tt.deviceid, 
    tt.devicecode, 
    dc.devicecategoryname,
    tt.sensorcode,
    tt.hop_level
FROM topology_tree tt
LEFT JOIN devicecategory dc ON dc.devicecategoryid = tt.devicecategoryid
WHERE tt.devicecategoryid IN (38, 47)
ORDER BY tt.hop_level ASC, tt.sensorcode ASC;