<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="975" height="460" viewBox="0 0 975 460" role="img" aria-labelledby="title description">
  <title id="title">phpont profile terminal</title>
  <desc id="description">A handcrafted terminal-style profile with ASCII skull artwork and developer information.</desc>
  <style>
    svg {
      font-family: Consolas, "Liberation Mono", "Courier New", monospace;
      font-size: {{FONT_SIZE}}px;
      font-variant-ligatures: none;
    }
    text, tspan { white-space: pre; }
    .primary { fill: {{PRIMARY}}; }
    .muted { fill: {{MUTED}}; }
    .key { fill: {{KEY}}; }
    .value { fill: {{VALUE}}; }
  </style>
  <rect x="0" y="0" width="975" height="460" rx="14" fill="{{BACKGROUND}}" stroke="{{BORDER}}"/>
  <clipPath id="ascii-viewport"><rect x="0" y="18" width="365" height="420"/></clipPath>
  <g clip-path="url(#ascii-viewport)">{{ASCII_MARKUP}}</g>
  <g>{{INFO_MARKUP}}</g>
</svg>
