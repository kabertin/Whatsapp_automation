import cv2
import gc
import os

def validate_rwanda_id(image_path):
    print(f"DEBUG: Processing {image_path}")
    try:
        # Check if file actually exists
        if not os.path.exists(image_path):
            print(f"ERROR: File not found at {image_path}")
            return {"error": "File not found on server"}

        # Load image in grayscale immediately to save RAM
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"error": "Invalid image format"}

        # Resize to very small for verification to prevent RAM spikes
        img = cv2.resize(img, (500, 300))

        # For now, if we can open and resize it, we treat it as valid
        # This UNSTOPS your workflow so you can continue building
        return {
            "id_number": "PENDING_MANUAL_REVIEW",
            "status": "valid",
            "side": "Front"
        }

    except Exception as e:
        print(f"CRITICAL VALIDATOR ERROR: {str(e)}")
        return {"error": f"Internal processing error: {str(e)}"}
    finally:
        gc.collect()
