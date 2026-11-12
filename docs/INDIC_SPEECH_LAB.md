# Indic Speech Lab & Normalization Specification

## 1. Problem Statement
Evaluating speech recognition models on Indian languages using traditional Western WER (Word Error Rate) introduces severe measurement bias:
1. **Numeral Formats**: An ASR model transcribing `5000` when the reference text uses Devanagari `५,०००` incurs a 100% word penalty despite being semantically identical.
2. **Punctuation Variations**: Dandas (`।`, `॥`) vs ASCII periods (`.`) cause artificial mismatches.
3. **Unicode Non-Equivalence**: Devanagari combined vowel matras can exist as precomposed code points or decomposing sequences.
4. **Code-Switching (Hinglish/Tanglish)**: Casual conversational speech interleaves English loanwords with Indic syntax, confounding single-language lexicons.

---

## 2. Indic Normalization Pipeline
VoxLab implements a rigorous, reversible text normalizer located at `backend/app/indic/normalization.py`.

### Pipeline Steps:
1. **Unicode NFC Canonical Decomposition**: Eliminates glyph-level divergence.
2. **Indic-to-Arabic Numeral Transliteration**:
   - Devanagari: `०१२३४५६७८९` -> `0123456789`
   - Bengali: `০১২৩৪৫৬৭৮৯` -> `0123456789`
   - Tamil: `௦௧௨௩௪௫௬௭௮௯` -> `0123456789`
3. **Digit Comma Collapsing**: Transforms currency formatting (`5,000` -> `5000`) to prevent whitespace token segmentation errors.
4. **Punctuation & Currency Stripping**: Removes `₹`, `।`, `॥`, quotes, and standard ASCII punctuation.
5. **Whitespace Canonicalization**: Normalizes spaces and trims whitespace.

---

## 3. Dual-Layer Evaluation Metrics
VoxLab computes two parallel metrics for every Indic evaluation:
- **Raw Verbatim Metric**: Standard edit distance on unnormalized text. Reflects exact typographical match.
- **Normalized Indic Metric**: Scored after applying the Indic Normalization pipeline. Reflects true acoustic & semantic recognition fidelity.
- **Code-Switching Ratio**: Percentage of Latin characters vs native Indic script characters in the utterance.
- **Loanword Accuracy**: Precision tracking whether specified English technical loanwords (e.g., `refund`, `login`, `account`) survived transcription.

