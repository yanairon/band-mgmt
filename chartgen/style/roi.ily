% roi.ily - Roi's chart house style (measured from his engraved charts).
% Include from a generated chart file. Defines:
%   \roiPaper        - A4, no tagline, full justification, bold title/composer title markup
%   \roiLayout       - chord-name font, thin staff lines, bar numbers at system starts
%   \roiSlashStencil - stemless mid-staff slash (measured geometry)
%   \boxMark         - boxed section label
%   \boxMarkNum      - boxed section label with the start bar number folded in
%   \roadmapBox      - centered boxed roadmap line between sections
%   \majSeven        - inline "maj7" chord suffix
\version "2.24.4"
#(set-global-staff-size 18)

roiPaper = \paper {
  #(set-paper-size "a4")
  tagline = ##f
  ragged-last = ##f
  ragged-right = ##f
  system-system-spacing.basic-distance = #17
  system-system-spacing.minimum-distance = #10
  bookTitleMarkup = \markup \column {
    \fill-line { \bold \abs-fontsize #20 \fromproperty #'header:title }
    \vspace #0.5
    \fill-line { \null \bold \abs-fontsize #13 \fromproperty #'header:composer }
  }
}

% Stemless slash noteheads, measured pixel-wise from Roi's charts:
% ~2.1 staff-spaces wide, ~2.4 tall, ~50 deg, hairline, centered on the
% middle staff line, one per beat.
roiSlashStencil = #(lambda (grob)
  (ly:stencil-translate
    (make-path-stencil '(moveto 0 0 lineto 1.9 2.3) 0.27 1 1 #f)
    (cons -0.95 -1.15)))

roiLayout = \layout {
  \context {
    \ChordNames
    % upright, normal-weight roman chord names, inline, with air above the staff
    \override ChordName.font-family = #'roman
    \override ChordName.font-shape = #'upright
    \override ChordName.font-series = #'normal
    \override ChordName.font-size = #0.5
    \override VerticalAxisGroup.nonstaff-relatedstaff-spacing.padding = #2.5
  }
  \context {
    \Voice
    % slash notation carries no stems
    \override Stem.stencil = ##f
  }
  \context {
    \Score
    % bar numbers only at system starts
    \override BarNumber.break-visibility = ##(#f #f #t)
    \override RehearsalMark.self-alignment-X = #LEFT
    % thin staff lines, light volta brackets
    \override StaffSymbol.thickness = #0.75
    \override VoltaBracket.thickness = #1.0
  }
}

boxMark = #(define-music-function (text) (string?)
  #{ \mark \markup { \override #'(box-padding . 0.5) \box \bold #text } #})

boxMarkNum = #(define-music-function (text num) (string? string?)
  #{ \mark \markup \column {
       \override #'(box-padding . 0.5) \box \bold #text
       \vspace #0.2
       \line { \override #'(font-size . -3) #num }
     } #})

roadmapBox = #(define-scheme-function (text) (string?)
  #{ \markup { \vspace #1.2 \fill-line { \override #'(box-padding . 0.5) \box \bold #text } \vspace #1.2 } #})

majSeven = { \set majorSevenSymbol = \markup \raise #-0.75 { "maj7" } }
