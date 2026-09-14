# Findings

Things that cost real debugging on this dataset. Worth reading before writing
any version of the ingest code, because several of these fail silently rather
than loudly.

## The data

**The submission date is not `update_date`.** `update_date` is the last time
the record was touched, which for an active paper can be years after
submission. The real date is in `versions[1].created`, RFC-822 formatted:

    try_strptime(versions[1].created, '%a, %-d %b %Y %H:%M:%S GMT')::DATE

Verified `%-d` parses both single- and double-digit days. The first record in
the snapshot was submitted 2007-04-02 with `update_date` 2008-11-26, so any
"papers per year" chart built on `update_date` measures revision activity.

If the bulk load does `SELECT * EXCLUDE (versions, authors_parsed)`, this field
is gone before you notice you needed it.

**`categories` is a space-separated VARCHAR**, e.g. `"hep-ph gr-qc"`. Not a
list. `UNNEST(categories)` fails with *"UNNEST() can only be applied to lists,
structs and NULL, not VARCHAR"*. Use `string_split(categories, ' ')` first.
This also means `WHERE categories = 'hep-th'` only matches papers that have
exactly one category.

**Titles and abstracts contain newlines** from the source line-wrapping.
DuckDB's `trim()` strips spaces only, not newlines, so collapse first and trim
after: `trim(regexp_replace(x, '\s+', ' ', 'g'))`.

**Columns that are null throughout the inference sample get typed JSON**, not
VARCHAR, and then break the insert. Cast every column explicitly in the load
query rather than relying on `read_json_auto` inference.

**The snapshot is ordered by arXiv ID**, and new-style IDs (`0704.0001`) sort
before old-style ones (`hep-th/9901001`). So a `LIMIT 200000` prefix is all
2007-2010 papers, not a chronological sample. The 1990s material is deep in
the file.

**Size**: ~1350 bytes per row in DuckDB. The 4.9 GB JSON holds ~2.8M rows;
about 13% of each line is `authors_parsed` + `versions` and another 10% is
field names repeated per line. Full load lands around 3.5 GB.

## The taxonomy

**`physics.plasma-ph` does not exist.** arXiv's abbreviation is `plasm-ph`, so
the code is `physics.plasm-ph`. Confirmed against the data: 1,177 papers on
`physics.plasm-ph`, zero on `physics.plasma-ph`.

**Nonlinear Sciences (`nlin.*`) is a whole top-level archive** and is easy to
miss entirely. Also commonly missing: `cs.NA`, `physics.atom-ph`.

**Bare archive names appear on older papers.** astro-ph had no subcategories
until 2009, so pre-2009 papers carry just `astro-ph`. Same for `cond-mat`,
`q-bio`, `nlin`. In the first 200k rows alone that is ~20,000 papers.

**18 retired codes** appear on pre-2007 papers: `cmp-lg`, `chao-dyn`,
`alg-geom`, `q-alg`, `solv-int`, `mtrl-th`, `funct-an`, `dg-ga`, `adap-org`,
`comp-gas`, `patt-sol`, `acc-phys`, `ao-sci`, `atom-ph`, `bayes-an`,
`chem-ph`, `plasm-ph`, `supr-con`.

**An inner join against the taxonomy silently drops all of the above.** Use a
left join and log what failed to map, or papers disappear from your counts
with no error.

**Alias pairs double-count cross-listed papers**: `cs.IT`/`math.IT`,
`cs.LG`/`stat.ML`, `cs.NA`/`math.NA`, `cs.SY`/`eess.SY`, `econ.GN`/`q-fin.EC`,
`math.MP`/`math-ph`, `math.ST`/`stat.TH`. Group on a canonical code, not the
raw one.

## DuckDB

**One read-write process at a time.** A writer holds an exclusive file lock, so
a long-lived write connection in the web layer blocks any batch job and vice
versa. Readers must pass `read_only=True`.

**Never materialise the staging table in pandas.** `con.execute("SELECT * FROM
temp").df()` on 2.8M rows with abstracts is 10+ GB of RAM and gets OOM-killed
on a laptop. Run not-null and uniqueness checks as SQL aggregates; keep pandera
for a sample.

**`INSERT ... SELECT ... QUALIFY ... ON CONFLICT` works** and is the right
shape. The window function collapses duplicate ids inside the batch so
`ON CONFLICT DO UPDATE` never has to touch the same row twice:

    INSERT INTO papers (cols) SELECT cols FROM staging
    QUALIFY row_number() OVER (PARTITION BY id ORDER BY update_date DESC) = 1
    ON CONFLICT (id) DO UPDATE SET ...

**`VACUUM` does not reclaim disk space** in DuckDB the way it does in SQLite.

**Replacement scans read local variables**, so `FROM my_df` works inside a
function. Interpolating the DataFrame into an f-string does not: it writes the
repr into the SQL and fails at the parser.

**Parameterised paths work**: `read_json_auto(?)` accepts a bound parameter.

## Tooling

**MCP Python SDK is at 2.x**, where `FastMCP` was renamed to `MCPServer`.
`from mcp.server.fastmcp import FastMCP` no longer exists. Annotation fields
are snake_case: `read_only_hint`, not `readOnlyHint`. Most tutorials online
still show the 1.x API.

**Do not commit a full `pip freeze`.** Pinning transitive dependencies means
every new package eventually collides with a pin you never chose. Declare
direct dependencies only; use a lockfile if you need reproducibility.

**Keep the 4.9 GB snapshot out of git.** GitHub rejects files over 100 MB and
it is painful to remove from history afterwards.
