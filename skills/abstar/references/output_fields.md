# abstar AIRR output fields (v0.8.0)

Each annotated sequence has 147 fields in `airr/*.tsv` (and the Parquet). Grouped:

## Identifiers & metadata
`sequence_id`, `locus` (IGH/IGK/IGL/TRA/TRB…), `species`, `germline_database`,
`sequence_input`, `sequence_oriented`, `rev_comp`, `frame`, `umi`, `quality`

## Gene calls (per segment: v, d, j, c)
`{seg}_call` (allele, AIRR standard, may be comma-separated), `{seg}_gene` (allele-free),
`{seg}_score`, `{seg}_support`, `{seg}_cigar`, `{seg}_sequence`, `{seg}_germline`,
`{seg}_sequence_start/end`, `{seg}_germline_start/end`

## Regions (nucleotide + `_aa`)
`fwr1`, `cdr1`, `fwr2`, `cdr2`, `fwr3`, `cdr3`, `fwr4`, `junction`, `junction_aa`,
`cdr3_length`. CDR3 decomposed into `cdr3_v`, `cdr3_n1`, `cdr3_d`, `cdr3_n2`, `cdr3_j`
(each with `_aa`). Masks: `cdr_mask`, `gene_segment_mask`, `nongermline_mask` (+ `_aa`).

## Junctional diversity
`np1`, `np2` (non-templated nt between segments) and `np1_length`, `np2_length`

## Somatic hypermutation (SHM)
`{v,d,j,c}_identity` and `_identity_aa` (germline identity), `{v,c}_mutations` / `_aa`,
`{v,c}_mutation_count` / `_aa`, `{v,c}_insertions`, `{v,c}_deletions`, `v_frameshift`
> SHM% ≈ 100 − v_identity (v_identity may be a 0–1 fraction; normalize before displaying).

## Productivity / QC
`productive`, `complete_vdj`, `stop_codon`, `productivity_issues`

## Constant region / isotype
`c_call` is the isotype (e.g. IGHG1, IGHM) for BCR heavy chains; plus the full `c_*` gene/
mutation set. Often null for light chains.

## Full sequences (many variants)
Raw / oriented / IMGT-`gapped` / `alignment` forms, translated (`_aa`), and assembled
`sequence_vdjc` / `sequence_lvdjc` (leader+VDJC), each with matching `germline_*`.

## Quick polars recipe
Read AIRR TSV as strings to avoid dtype-inference errors on mask columns, then cast:
```python
import polars as pl
df = pl.read_csv(path, separator="\t", infer_schema_length=0)
df = df.with_columns(pl.col("cdr3_length").cast(pl.Int64, strict=False),
                     pl.col("v_identity").cast(pl.Float64, strict=False))
```
