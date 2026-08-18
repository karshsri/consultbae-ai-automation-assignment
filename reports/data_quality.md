# Data Quality Report

## Overview

The three source files contain overlapping people but no common identifier.
The pipeline preserves raw source records and applies explicit normalization
and matching rules before creating canonical people records.

## 1. Naukri Applicants

### Phone formatting
Phone values appear in multiple formats including country-code, +91,
leading-zero and 10-digit representations.

**Handling:** phone numbers are normalized to a canonical 10-digit form
before matching.

### City inconsistency
Cities contain casing and naming variants such as Bangalore/Bengaluru,
Gurgaon/Gurugram, Pune/pune/PUNE and Noida/NOIDA.

**Handling:** whitespace and casing are normalized and known aliases are
mapped explicitly.

### Duplicate identity records
Some people appear more than once with variations in name/email/phone.

**Handling:** normalized email and phone are used as high-confidence
identity signals. Duplicate source records are linked to the same person.

### Applied date formats
Dates use multiple formats.

**Handling:** raw dates are preserved during ingestion. Date normalization
can be applied downstream without changing the source record.

### Current CTC representation
CTC contains mixed-looking numeric representations.

**Handling:** the raw CTC value is preserved rather than applying an
unsupported unit conversion.

### Skills
Skill lists use inconsistent capitalization.

**Handling:** skills are split, lowercased, trimmed and stored as a
canonical JSON list.

---

## 2. Gig Workers

### Blank row
One completely empty record exists.

**Handling:** blank records are ignored during ingestion and are not
converted into people.

### Malformed shifted row
One record has fields shifted across columns.

**Handling:** the pipeline detects the pattern, reconstructs the fields,
and preserves the original raw row in `source_records`.

### Duplicate/ambiguous names
Names such as Deepak Nair can appear more than once with different
identifiers or locations.

**Handling:** name alone is never sufficient for an automatic merge.

### Status inconsistency
Status values contain casing differences and one malformed value caused
by the shifted row.

**Handling:** status is normalized after malformed-row handling.

### Skill formatting
Skills contain inconsistent capitalization.

**Handling:** canonical lowercase skill lists are created.

---

## 3. CBNexus Contacts

### Duplicate header row
A header-like row appears inside the data.

**Handling:** the row is detected and excluded.

### Verification values
Verification is represented using Y/N and Yes/No variants.

**Handling:** values are converted to boolean-style 1/0 values.

### City formatting
City values have casing and naming variations.

**Handling:** normalization and explicit aliases are applied.

### Ambiguous duplicate names
Arjun Mehta appears more than once with different phone numbers.

**Handling:** name alone is never used to merge records. Phone/email identity
signals take precedence.

---

## Matching policy

1. Exact normalized phone -> high-confidence match.
2. Exact normalized email -> high-confidence match.
3. Identity field plus matching name -> very high-confidence match.
4. Fuzzy name plus same normalized city -> fallback match.
5. Name alone -> never automatically merged.

Every source record retains its source, row number, raw values, match method
and confidence for auditability.