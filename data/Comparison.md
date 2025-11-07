# Comparison of Samples

## Gender

### Snowball sample (total records: 130)

| Gender | Count | Percent |
|---:|---:|---:|
| Male | 10 | 7.7% |
| Female | 112 | 86.2% |
| Unknown | 8 | 6.2% |

### Alphabet sample (total records: 130)

| Gender | Count | Percent |
|---:|---:|---:|
| Male | 55 | 42.3% |
| Female | 75 | 57.7% |
| Unknown | 0 | 0.0% |

## Age

### Snowball sample (n with age: 125)

| Metric | Value |
|---|---:|
| Records with age | 125 |
| Mean age | 34.11 |
| Median age | 33.00 |
| Age stdev | 5.78 |
| Min age | 22 |
| Max age | 53 |

### Alphabet sample (n with age: 130)

| Metric | Value |
|---|---:|
| Records with age | 130 |
| Mean age | 42.45 |
| Median age | 39.00 |
| Age stdev | 12.65 |
| Min age | 26 |
| Max age | 96 |

## Notes

- Gender is inferred using the `gender_inferred` field when present. Values were normalized to 'male', 'female', or 'unknown'.
- Age is taken from the `age` field when available; records without a parseable age were excluded from the age statistics.
- If a sample has few or no age values, mean/stdev may be unavailable.