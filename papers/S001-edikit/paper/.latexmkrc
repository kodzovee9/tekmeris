# latexmk settings for this paper directory.
#
# Why this exists: this directory holds three independent documents that
# each compile to a COMMITTED pdf - main.tex, cover_letter.tex, and
# figure1.tex. Given no filename, latexmk operates on every .tex in the
# directory, so a bare `latexmk -C` deletes all three committed PDFs, not
# just the one being rebuilt. The two collateral ones are not regenerated
# by the build that follows, so the loss is silent until someone notices a
# deliverable is missing. (This happened; they were restored from git.)
#
# Scoping the default target to main.tex means bare invocations only ever
# touch the paper itself. The cover letter and the figure are still
# buildable, but only when named explicitly:
#
#   latexmk cover_letter.tex      # build just the cover letter
#   latexmk -C cover_letter.tex   # clean just the cover letter
#
# To force a rebuild of main.pdf, prefer `latexmk -g` over `latexmk -C`:
# -g reprocesses regardless of the .fdb_latexmk cache without deleting
# anything, which is what "force a rebuild" almost always means. Reach for
# -C only to discard main.pdf deliberately.
@default_files = ('main.tex');

# Build PDF directly, so a bare `latexmk` does the right thing.
$pdf_mode = 1;
