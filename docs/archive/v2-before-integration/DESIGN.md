---
version: alpha
name: Quiz-Studio
description: >
  Offline Tkinter quiz shell using a Lights Out (dark) surface. Chromatic
  accent is reserved for primary actions, progress fills, and focus.
  Hairline cards on raised surfaces; no emoji fields, no mesh gradients.
  Tkinter approximates radius with padding; do not fake CSS pills.
  This document must stay aligned with learning_platform/ui_tokens.py.

colors:
  primary: "#1D9BF0"
  primary-hover: "#A7C3D4"
  primary-press: "#6E90A6"
  on-primary: "#FFFFFF"
  ink: "#E7E9EA"
  ink-mute: "#71767B"
  canvas: "#000000"
  canvas-band: "#161616"
  surface: "#16181C"
  raised: "#1D1F23"
  hairline: "#2F3336"
  track: "#161616"
  error: "#F4212E"
  error-soft: "#2A1216"
  success: "#00BA7C"
  success-soft: "#122018"

typography:
  mark:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 11px
    fontWeight: 600
  display:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 22px
    fontWeight: 600
  card-title:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 16px
    fontWeight: 600
  label:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 10px
    fontWeight: 400
  body:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 11px
    fontWeight: 400
  caption:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 9px
    fontWeight: 400
  button:
    fontFamily: "Microsoft YaHei UI"
    fontSize: 12px
    fontWeight: 600
  number:
    fontFamily: Consolas
    fontSize: 11px

rounded:
  sm: 8px
  md: 10px
  lg: 12px

spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 24px
  6: 32px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    padding: 12px 16px
  button-tertiary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: 8px 4px
  input:
    backgroundColor: "{colors.surface}"
    border: "1px {colors.hairline}"
    padding: 12px
  card:
    backgroundColor: "{colors.surface}"
    border: "1px {colors.hairline}"
    padding: 24px
    width: 420px

rules:
  - Quieter: no illustration noise, no fake multi-layer drop shadows, no rounded-pill bars.
  - Distill: brand column is mark + one line of copy + one progress card.
  - Typeset: display 22, card 16, body 11, caption 9; percents use Consolas.
  - Layout: split at 900px; form 420; tools and guest hit area at least 40px.
  - Chromatic fill only on the primary button, progress fill, and focus ring.
  - Login form must not live inside a Canvas window (IME / typing lag on Windows).
  - Password hashing runs off the UI thread; buttons may show a busy label only.
  - Motion is optional and defaults to off; scoring never waits on animation.
  - Keep auth, guest, i18n, and local storage behavior unchanged.
