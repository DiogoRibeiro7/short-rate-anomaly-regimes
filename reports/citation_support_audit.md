# Citation Support Audit

Verdict: `PASS_WITH_NARROWING`. The narrowing is discharged; see
"Required manuscript change" below.

| Manuscript Claim | Cited Source | Audit Decision |
|---|---|---|
| ICAPM state variables can earn premia because they forecast investment opportunities. | Merton 1973 | Supported as theoretical motivation. |
| The short-rate anomaly baseline follows Maio and Santa-Clara. | Maio and Santa-Clara 2017 | Supported by the registered article and supplement evidence manifest. |
| Two-pass tests require generated-regressor and weak-factor discipline. | Fama-MacBeth 1973; Shanken 1992; Kan-Zhang 1999; Lewellen-Nagel-Shanken 2010 | Supported. |
| Monetary-regime and announcement decompositions require separate identification language. | Bernanke-Kuttner 2005; Jarocinski-Karadi 2020; Swanson-Williams 2014 | Supported when phrased as motivation, not as evidence for this paper's aggregate AR residual. |
| Kenneth French Data Library supports factor and portfolio availability and version discipline. | Kenneth French Data Library | Supported only when narrowed to current data-library availability and explicit historical-archive or CRSP-change documentation. Do not cite it as proof that every historical revision is fully documented. |

Required manuscript change: replace broad claims about "historical revisions"
with a narrower claim that official archives and change notes require vintage
recording before exact replication or post-publication comparisons are labelled.

Status: discharged. The requirement stands as written above and is retained so
that any future rewrite of the data-vintage stream can be checked against it.

The narrowed claim now lives in the final paragraph of `Related literature` in
`paper/manuscript.tex`, the only place where
`\citep{fama_french_data_library_2026}` is used. That paragraph states that
official factor libraries publish current data, dated historical archives, and
selected change notes "rather than a complete revision history, so the retrieval
vintage of a source has to be recorded before an estimate is labelled an exact
replication or entered into a post-publication comparison". The citation is
therefore attached to library availability and to the vintage-recording
obligation, not to a claim that every historical revision is documented.

No other citation of the data library exists, and no other passage in the
literature, methods, or data sections cites it in support of revision
completeness. Vintage statements elsewhere in the manuscript are claims about
this paper's own frozen retrieval vintages and its vintage-isolation comparison,
which rest on repository artifacts rather than on the data-library citation.
