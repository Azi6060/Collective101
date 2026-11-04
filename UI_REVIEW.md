# Collective101 UI review handoff

Prepared 5 November 2026 (Asia/Kuala_Lumpur). These manual checks are for the teammate and remain **pending**. See [README](README.md) for setup, [PROJECT_STATUS](PROJECT_STATUS.md) for scope and [VERIFICATION](VERIFICATION.md) for dated automated results. Latest work is local on `work/main-updates`; nothing is automatically published or merged into main.

Open the [local app](http://127.0.0.1:8765/), or follow README setup on your computer. Accounts belong to that computer's shared runtime database, not a hosted service. Create the first owner only on the intended workspace. Never include credentials/private uploads in review notes.

## Screenshots

These use disposable scripted-provider state; they are interface examples, not evidence of live AI competence.

- [Saved-work search](docs/review/saved-work-search.png)
- [Recovered draft on mobile](docs/review/draft-mobile.png)
- [Compact Light-mode voice player](docs/review/voice-light.png)

## Manual checklist

- [ ] Home explains the project; Dashboard transfers an editable draft to Chat without sending. Header navigation and Settings are easy to find on desktop/phone.
- [ ] Recent chats search finds names and saved/uploaded filenames in the latest 100 chats. Loading/no-result states are clear. It does not search document contents.
- [ ] Rename a chat through the pencil in Files & activity. History/workspace update while the original conversation stays unchanged. Filename matches open the right filtered Files/Uploads tab.
- [ ] Type separate new-chat, follow-up and Dashboard drafts; refresh/switch and verify each restores correctly with completed attachment references. Discard and accepted sends clear the right entry. Sign-in/out clears tab drafts.
- [ ] Upload supported text/media and check size, transfer progress, completion and original download. Cancel/Retry/Remove preserve completed files. Resolve failed/cancelled queue entries before sending. Unfinished selections are not restored after reload.
- [ ] Test offline/reconnect feedback. A failed send retains its draft; an unchanged retry retains its request ID. Check saved history if uncertain whether the original send succeeded. Recovery failures block Send until explicit Retry/Discard.
- [ ] On your own device, allow microphone access and check speech-to-text both on/off, accuracy/language, denied/no-mic states and measured waveform response. Optional browser transcription may process audio remotely.
- [ ] Listen to local recording replay and read-aloud through actual speakers/headphones. Pause/seek/delete/Stop should work. Leaving Chat/hiding the tab stops capture/playback. Clips are ephemeral, capped at two minutes and never sent to agents.
- [ ] Check Light/Dark/System, larger text, reduced motion and language selection, including Arabic layout. English is default; untranslated detailed messages retain English and agent content keeps its original language. Native-speaker review remains needed.
- [ ] Check Tab/Shift+Tab, Enter/Escape, search ArrowDown, dialog focus return and Files/Uploads/Activity arrows. Verify visible focus, screen-reader labels if available and 200% zoom.
- [ ] On a phone, open the software keyboard with a recovered draft/attachments and test portrait/landscape scrolling and reachable composer actions. Inspect text/icons and disabled/hover/focus contrast in both themes.
- [ ] Test account creation/sign-in/profile/sign-out and the current-user avatar. Owner invitations control member registration. Members share this local workspace's chats/files/connectors/operator controls.

## Live work and findings

The maintained app's model is still unconfigured. Local search/drafts/recording/preferences need no model call; new AI replies do. Configure and authorize live work separately before any paid mission/evaluation. Do not replay historical failed work or present fixtures as live results. Images/video/PDF remain reference-only for the current text model.

Report page, browser/OS, screen size, steps, expected/actual result and blocking/usability/cosmetic severity. Crop screenshots to exclude passwords, keys, sensitive text and private files. Synthetic Chrome audio/viewport checks do not certify actual devices, speech recognition, audible output or full accessibility.

The existing held-out-role expectation issue remains documented; do not widen runtime permissions to make it pass. Hosted accounts, audio delivery to agents, multimodal analysis and full accessibility certification are outside this handoff. Teammate approval does not merge or publish anything automatically.
