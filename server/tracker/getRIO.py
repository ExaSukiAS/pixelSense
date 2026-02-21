import cv2
import os

base_dir = os.path.dirname(__file__)
image_path = os.path.join(base_dir, "sampleData/screwdriver/frame_00000.jpg")

img = cv2.imread(image_path)

if img is None:
    print("Error: Could not load image.")
    exit()

# Select ROI (returns x, y, w, h)
roi = cv2.selectROI("Select Object", img, showCrosshair=True, fromCenter=False)
cv2.destroyWindow("Select Object")

x, y, w, h = roi

if w == 0 or h == 0:
    print("No ROI selected.")
    exit()

imgHeight, imgWidth, _ = img.shape

# Normalize to (xmin, xmax, ymin, ymax)
norm_xmin = x / imgWidth
norm_xmax = (x + w) / imgWidth
norm_ymin = y / imgHeight
norm_ymax = (y + h) / imgHeight

print("Normalized ROI (xmin, xmax, ymin, ymax):")
print(f"({norm_xmin:.6f}, {norm_xmax:.6f}, {norm_ymin:.6f}, {norm_ymax:.6f})")

# Optional: draw rectangle
cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
cv2.imshow("Selected ROI", img)
cv2.waitKey(0)
cv2.destroyAllWindows()