-- Report birth coordinates that point at the wrong place. Read-only; empty output means clean.
--
--   sqlite3 awards.sqlite3 < scripts/check_coordinates.sql
--
-- Spec: docs/birth-coordinates-validation-20260725.md. Each row starts with the check that flagged it.
-- 0.3 degrees keeps checks 1 and 2 quiet about city-vs-municipality entities.

.mode list
.separator ' | '

-- 1. same full_name, coordinates more than 0.3 degrees apart
WITH c AS (
    SELECT award_record_id AS id, full_name, birth_city, birth_coordinates AS xy,
           CAST(substr(birth_coordinates, 1, instr(birth_coordinates, ',') - 1) AS REAL) AS lon,
           CAST(substr(birth_coordinates, instr(birth_coordinates, ',') + 1) AS REAL) AS lat
    FROM awards WHERE COALESCE(birth_coordinates, '') <> ''
)
SELECT 'same_name', a.id, b.id, a.full_name, a.birth_city || ' ' || a.xy, b.birth_city || ' ' || b.xy
FROM c a JOIN c b ON a.full_name = b.full_name AND a.id < b.id
WHERE abs(a.lon - b.lon) > 0.3 OR abs(a.lat - b.lat) > 0.3
ORDER BY a.full_name, a.id;

-- 2. same (birth_city, birth_country), coordinates more than 0.3 degrees apart
WITH c AS (
    SELECT award_record_id AS id, full_name, birth_city, birth_country, birth_coordinates AS xy,
           CAST(substr(birth_coordinates, 1, instr(birth_coordinates, ',') - 1) AS REAL) AS lon,
           CAST(substr(birth_coordinates, instr(birth_coordinates, ',') + 1) AS REAL) AS lat
    FROM awards WHERE COALESCE(birth_coordinates, '') <> '' AND COALESCE(birth_city, '') <> ''
)
SELECT 'same_city', a.id, b.id, a.birth_city || ', ' || a.birth_country, a.full_name || ' ' || a.xy, b.full_name || ' ' || b.xy
FROM c a JOIN c b ON a.birth_city = b.birth_city AND a.birth_country = b.birth_country AND a.id < b.id
WHERE abs(a.lon - b.lon) > 0.3 OR abs(a.lat - b.lat) > 0.3
ORDER BY a.birth_city, a.id;

-- 3. longitude sign wrong for the country. Lists are deliberately partial; extend as countries appear.
--    Countries straddling the prime meridian (United Kingdom, France, Spain, Algeria, ...) are left out.
WITH c AS (
    SELECT award_record_id AS id, full_name, birth_city, birth_country, birth_coordinates AS xy,
           CAST(substr(birth_coordinates, 1, instr(birth_coordinates, ',') - 1) AS REAL) AS lon
    FROM awards WHERE COALESCE(birth_coordinates, '') <> ''
)
SELECT 'lon_sign', id, full_name, birth_city || ', ' || birth_country, xy
FROM c
WHERE (lon > 0 AND birth_country IN (
           'United States', 'Canada', 'Mexico', 'Cuba', 'Guatemala', 'Puerto Rico', 'Jamaica', 'Trinidad and Tobago',
           'Brazil', 'Argentina', 'Chile', 'Colombia', 'Peru', 'Venezuela', 'Uruguay', 'Bolivia', 'Ecuador', 'Paraguay'))
   OR (lon < 0 AND birth_country IN (
           'Germany', 'Italy', 'Netherlands', 'Belgium', 'Switzerland', 'Austria', 'Denmark', 'Sweden', 'Norway', 'Finland',
           'Poland', 'Czech Republic', 'Slovakia', 'Hungary', 'Romania', 'Bulgaria', 'Greece', 'Croatia', 'Serbia', 'Slovenia',
           'Ukraine', 'Belarus', 'Russia', 'Lithuania', 'Latvia', 'Estonia', 'Turkey', 'Israel', 'Egypt', 'Iran', 'India',
           'Pakistan', 'Bangladesh', 'China', 'Taiwan', 'Hong Kong', 'Japan', 'South Korea', 'Vietnam', 'Thailand',
           'Singapore', 'Indonesia', 'Philippines', 'Australia', 'New Zealand', 'South Africa'))
ORDER BY id;

-- 4. birth_city appears inside full_name: a surname geocoded as the birthplace
SELECT 'city_in_name', award_record_id, full_name, birth_city, birth_coordinates
FROM awards
WHERE COALESCE(birth_coordinates, '') <> '' AND COALESCE(birth_city, '') <> '' AND instr(full_name, birth_city) > 0
ORDER BY award_record_id;

-- 5. not longitude,latitude at four decimals, or out of range
WITH c AS (
    SELECT award_record_id AS id, full_name, birth_coordinates AS xy,
           substr(birth_coordinates, 1, instr(birth_coordinates, ',') - 1) AS x,
           substr(birth_coordinates, instr(birth_coordinates, ',') + 1) AS y
    FROM awards WHERE COALESCE(birth_coordinates, '') <> ''
)
SELECT 'format', id, full_name, xy
FROM c
WHERE instr(xy, ',') = 0
   OR ltrim(x, '-') NOT GLOB '[0-9]*.[0-9][0-9][0-9][0-9]' OR ltrim(x, '-') GLOB '*[^0-9.]*' OR x GLOB '*.*.*' OR x GLOB '?*-*'
   OR ltrim(y, '-') NOT GLOB '[0-9]*.[0-9][0-9][0-9][0-9]' OR ltrim(y, '-') GLOB '*[^0-9.]*' OR y GLOB '*.*.*' OR y GLOB '?*-*'
   OR abs(CAST(x AS REAL)) > 180 OR abs(CAST(y AS REAL)) > 90
ORDER BY id;
