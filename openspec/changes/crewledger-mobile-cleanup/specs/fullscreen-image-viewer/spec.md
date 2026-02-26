## ADDED Requirements

### Requirement: Fullscreen image viewer overlay
The system SHALL display receipt images in a fullscreen dark overlay when the user taps the thumbnail in the receipt detail card.

#### Scenario: Open fullscreen viewer
- **WHEN** user taps the receipt thumbnail image in the detail modal
- **THEN** a fullscreen overlay appears with dark background and the image displayed at full size with object-fit:contain

#### Scenario: Close fullscreen viewer via X button
- **WHEN** user taps the X close button in the fullscreen viewer
- **THEN** the viewer closes and the user returns to the receipt detail card with state preserved

#### Scenario: Close fullscreen viewer via swipe down
- **WHEN** user swipes down on the fullscreen image
- **THEN** the viewer closes and returns to the detail card

#### Scenario: Pinch to zoom
- **WHEN** user pinch-zooms on the fullscreen image
- **THEN** the browser native pinch-zoom behavior applies via touch-action:pinch-zoom

#### Scenario: No swipe navigation in viewer
- **WHEN** user swipes left or right in the fullscreen viewer
- **THEN** nothing happens — receipt navigation only works at the detail card level
