# Confidence Threshold Slider Feature

## Overview
Implemented a confidence threshold slider that allows users to filter out low-probability category and keyword matches from AI model results. The threshold is configurable on a scale of 1-100 and applies to both category and keyword tagging.

## Changes Made

### 1. Session Configuration (`src/core/session.py`)
- Added `confidence_threshold: int = 50` field to `EngineConfig` dataclass
- Default value set to 50 (representing 50% confidence)
- Stores threshold as integer from 1-100 for UI purposes

### 2. Processing Logic (`src/core/processing.py`)
- Modified `_process_single_item()` method to pass threshold to tag extraction
- Converts threshold from 1-100 scale to 0.0-1.0 scale for model compatibility
- Threshold is applied during tag extraction: `threshold = engine.confidence_threshold / 100.0`

### 3. User Interface (`src/ui/steps/step2_tagging.py`)
- Added threshold slider section to `ConfigDialog` below the tabview
- Slider appears across all engine provider tabs (Local, Hugging Face, OpenRouter)
- Real-time value display showing current threshold percentage
- Descriptive label: "Filters out low-probability category/keyword matches"
- Slider range: 1-100 with 99 steps for precise control
- Callback method `on_threshold_change()` updates both UI and session in real-time

## How It Works

1. **User Configuration**: Users adjust the slider in the Engine Configuration dialog
2. **Value Storage**: The threshold value (1-100) is stored in `session.engine.confidence_threshold`
3. **Processing**: During image processing, the threshold is converted to 0.0-1.0 scale
4. **Filtering**: The `extract_tags_from_result()` function filters out:
   - Categories with probability scores below the threshold
   - Keywords with probability scores below the threshold
5. **Result**: Only high-confidence tags are written to image metadata

## Example Usage

- **Threshold = 50%**: Balanced filtering, removes moderately uncertain tags
- **Threshold = 90%**: Strict filtering, only very confident tags are kept
- **Threshold = 10%**: Lenient filtering, most tags are kept

## Technical Details

### Threshold Application
The threshold is applied in `src/core/image_processing.py` in the `extract_tags_from_result()` function:

```python
# For image classification (keywords)
if item['score'] >= threshold:
    keywords.append(item['label'])

# For zero-shot classification (categories)
if item['score'] >= threshold:
    matched_categories.append(item['label'])
```

### UI Components
- **Slider**: `CTkSlider` with range 1-100
- **Value Label**: Dynamic label showing current percentage
- **Description**: Helpful text explaining the feature
- **Callback**: Real-time updates to session configuration

## Benefits

1. **Quality Control**: Filters out uncertain predictions
2. **Customizable**: Users can adjust based on their needs
3. **Universal**: Applies to all AI providers (Local, Hugging Face, OpenRouter)
4. **User-Friendly**: Simple slider interface with clear feedback
5. **Optional**: Default value of 50% provides balanced filtering

## Branch Information
- **Branch Name**: `feature/confidence-threshold-slider`
- **Commit**: 6360f46
- **Files Modified**: 3
- **Lines Added**: 50
- **Lines Removed**: 1
