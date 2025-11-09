from typing import Optional, Tuple

# Holds latest GPS coordinate pushed from /update_location
# Format: (latitude, longitude)
LAST_LOCATION: Optional[Tuple[float, float]] = None