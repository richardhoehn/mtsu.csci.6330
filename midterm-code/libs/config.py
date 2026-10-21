#################################################
# *** Config File - Shared Across the Libs ***  #
#################################################

# ----------------------------
# Truck / Route Constraints
# ----------------------------
MAX_WEIGHT = 60_000 # Maximum truck payload in pounds (lbs)
MAX_DRIVE = 900     # Maximum driver drive time in minutes (900min = 15hours)
MAX_DIST = 999_999  # Maximum route distance in miles; intentionally set very high
MAX_PALLET = 99     # Maximum number of pallet positions available on the truck


# ----------------------------
# Driving / Fuel Efficiency
# ----------------------------
BASE_MPG = 6.5        # Fuel efficiency (MPG) when the truck has little/no payload
MIN_MPG = 2.5         # Minimum fuel efficiency (MPG) as payload becomes very heavy

MIN_PER_DIST = 60 / 55
# Estimated driving time in minutes per mile based on an average speed of 55 MPH


# Payload weight where MPG is halfway between BASE_MPG and MIN_MPG
MPG_HALF_WEIGHT = MAX_WEIGHT / 2


# ----------------------------
# Operating Costs
# ----------------------------
COST_PER_DRIVE = 25 / 60
# Driver labor cost per minute based on $25/hour

COST_PER_GAL = 7.50
# Estimated diesel fuel cost per gallon
# Estimate set 2026-10-07 by RH
