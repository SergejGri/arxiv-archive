**Background & Idea**
Whenever I am on arxiv.org, I fall into a rabit whole where I cannot stop jumping from one aper to another and then check buzzwords and e.g. asking myself:
1) how many papers has author x published on this topic?
2) when was the very first paper to topic x?
3) has the number (median) of authors on a paper has changed over time?
...

Sure it is possible to make your own research be checking back and for, but I want a dashboard, where my questions are answered with as near as possible to one-click-experiance

**Goals**
- I want to build a dashboard to enable an user to search trough arxiv papers and created its own graphs besides predefined (obsious) graphs like published papers per month over the whole time period.
- This is not done via http but from a offline copy of the arxiv papers.
- XML in JSON converter. arxiv data comes in XML, but data input in DuckDB is in json.
- I do not plan to make it public yet, so it is expected one user at time on this application.
- Feature: finding individual papers, like "show me papers about topic X" via a MCP server. I want have an option for search by cathegory and by buzzwords.
- I will build a mapper after meta data is fetched. A paper flagged as e.g. hep-ph in arxiv metadata should be made available for the user as "High Energy Physics - Phenomenology". THis way I have another "validation step" which helps to keep the db clean.
- Feature: failed validation, should be moved to quarantine table for user manually make reachers and update this papers metadata Failed records that need manual research. If validation finds dozents papers whose e.g. date doesn't parse. But count erros first. Systematic (many records, same cause): fix the code. Individual (a few odd records): the quarantine table, maybe manual review.
The manual-research workflow might belong under non-goals for version 1, with only the quarantine table kept. That's your call.
- I want an log function, which logs activities of the software depending on the set parameter (warning, errors, verbose for debugging)


**Dataflow**
- there is a bulk load json ~5GB of meta data. THis data goes into validation (stage table). After validation and transformation data goes into prod table. Validation in this case means, "counting" errors. check each date if parseable, hopw are the authors stored when multiple on one paper? Is the aothor columns per paper a single string? If so a "author seperator function" must be build.
- seperate table for authors
- probably seperate table for categories linked
- Then weekly fetches via arxiv API. Validation and the adding to prod.

**Schema**
column_name                                   column_type null   key default extra
0               id                                       VARCHAR  YES  None    None  None
1        submitter                                       VARCHAR  YES  None    None  None
2          authors                                       VARCHAR  YES  None    None  None
3            title                                       VARCHAR  YES  None    None  None
4         comments                                       VARCHAR  YES  None    None  None
5      journal-ref                                       VARCHAR  YES  None    None  None
6              doi                                       VARCHAR  YES  None    None  None
7        report-no                                       VARCHAR  YES  None    None  None
8       categories                                       VARCHAR  YES  None    None  None
9          license                                       VARCHAR  YES  None    None  None
10        abstract                                       VARCHAR  YES  None    None  None
11        versions  STRUCT("version" VARCHAR, created VARCHAR)[]  YES  None    None  None
12     update_date                                          DATE  YES  None    None  None
13  authors_parsed                                   VARCHAR[][]  YES  None    None  None


