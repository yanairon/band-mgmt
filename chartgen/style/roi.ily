% roi.ily - Roi's chart house style (from "Something v3" / Shine On reference).
% Include from a generated chart file. Defines:
%   \roiPaper   - A4 paper block, no tagline, system spacing
%   \roiLayout  - chord-name font, thin staff lines, bar numbers at system starts
%   \roiScore   - expects \chartChordLine, \chartMarks, \chartSlashes, \chartInstrument
\version "2.24.4"
#(set-global-staff-size 18)

roiPaper = \paper {
  #(set-paper-size "a4")
  tagline = ##f
  system-system-spacing.basic-distance = #17
  system-system-spacing.minimum-distance = #10
}

% Long thin slash noteheads (Roi's slashes)
roiSlashStencil = #(lambda (grob)
  (ly:stencil-scale (ly:note-head::print grob) 0.55 1.6))

roiLayout = \layout {
  \context {
    \ChordNames
    % upright, normal-weight roman chord names, inline
    \override ChordName.font-family = #'roman
    \override ChordName.font-shape = #'upright
    \override ChordName.font-series = #'normal
  }
  \context {
    \Score
    % bar numbers only at system starts
    \override BarNumber.break-visibility = ##(#f #f #t)
    \override RehearsalMark.self-alignment-X = #LEFT
    % thin staff lines
    \override StaffSymbol.thickness = #0.75
  }
}
