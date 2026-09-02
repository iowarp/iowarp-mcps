---
name: surveying-literature-and-datasets
description: Use when a literature answer would be given from memory, which confidently cites papers that do not exist and misses everything published recently. Covers finding prior work and the data behind published results. Triggers on "find papers on", "what is the literature", "prior work". Not for assembling citations; use building-a-bibliography. Not for staging a known dataset; use finding-and-staging-a-dataset.
clio-kit:
  bundle: clio-research
  servers: clio-arxiv, clio-ndp, clio-web
  provenance: designed
  eval-status: eval-run
---

# Survey a topic, then find the data behind it

ArXiv exposes seven search tools. They are not variations on one another, and
defaulting to `search_arxiv` for every question is the main way this goes wrong.

## Pick the search that matches the question

| The question | Tool |
|---|---|
| What exists on this topic | `clio-arxiv:search_arxiv` |
| Work by this person | `clio-arxiv:search_papers_by_author` |
| I know roughly the title | `clio-arxiv:search_by_title` |
| Papers whose *content* is about X | `clio-arxiv:search_by_abstract` |
| Everything in this field | `clio-arxiv:search_by_subject` |
| What has happened since | `clio-arxiv:search_date_range` |
| What is new in this field | `clio-arxiv:get_recent_papers` |

`search_by_abstract` is the one to reach for on a research question. Title search
finds papers that named the thing; abstract search finds papers that did it. For
any concept named inconsistently across a field, they return different sets.

Subject search needs the ArXiv category code (`astro-ph.GA`, `cs.DC`). Do not
guess one — an invalid category returns nothing, which reads like "no such work
exists".

## Widen deliberately, not by repeating

A thin result set is a signal about the query, not the field. In order:

1. Try `search_by_abstract` if you used title search.
2. Try the field's other vocabulary. Terminology differs across communities for
   the same idea.
3. Take the closest paper and run `clio-arxiv:find_similar_papers` on it. This
   works from the paper's own categories and keywords, so it reaches work you had
   no term for.
4. Use `search_date_range` to separate "nothing exists" from "nothing recent".

## Read enough to be sure

`clio-arxiv:get_paper_details` for the full record of a specific paper.

Do not characterise a paper's findings from its title. If the claim matters, get
the PDF URL with `clio-arxiv:get_pdf_url`, or download it with
`clio-arxiv:download_paper_pdf`. `download_multiple_pdfs` handles several
concurrently with rate limiting — use it rather than a download loop, which will
get throttled.

Note that ArXiv is preprints. Many are peer reviewed later, some never are, and
versions change. Check the version and date before treating something as settled.

## Then find the data

A paper's results rest on data that is usually not in the paper.

1. `clio-ndp:list_organizations` — who publishes on the platform, which narrows
   a search that would otherwise be too broad.
2. `clio-ndp:search_datasets` — term-based or field-specific.
3. `clio-ndp:get_dataset_details` — the full metadata for one. Read this before
   staging: it says what the data is, and staging it is the expensive step.
4. `clio-ndp:stage_resource` — download it locally, returning `local_path`, size
   and content type.

**Nothing reads a dataset until it is staged.** The analysis servers take file
paths; `local_path` from `stage_resource` is what you pass them. A dataset that
has only been searched is a description, not a file. See
`exploring-an-unfamiliar-dataset` for what comes next.

For operator-registered datasets, `clio-scientific-catalog:scientific_dataset_search`
and `scientific_dataset_describe` cover a separate curated catalog — see
`finding-and-staging-a-dataset`.

## Confirming against the live web

`clio-web:search` and `clio-web:fetch` reach things ArXiv does not: a project
page, a software release, a dataset landing page. Use them to confirm a claim
about current state, since a preprint describes the world at submission time.

`fetch` converts HTML to Markdown with a size cap and timeout; `to_file=True`
writes it out rather than returning it inline, which is what you want for
anything long.

## What not to do

- Do not use `search_arxiv` for every question.
- Do not guess ArXiv subject codes.
- Do not report "no work exists" from one query.
- Do not summarise a paper's findings from its title.
- Do not loop `download_paper_pdf` where `download_multiple_pdfs` exists.
- Do not treat a preprint as peer reviewed.
- Do not try to analyse a dataset that has not been staged.
