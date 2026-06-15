# MBTA Commute Optimizer

A real-time Python dashboard designed to help you decide the fastest way to get to the T. It compares walking
directly to the train station against taking the configurable bus routes, accounting for real-time traffic and train
schedules.

## Features

- Smart "Leave In" Countdown: Tells you exactly when to walk out the door, including a safety buffer.
- Live Bus Status: Displays exactly where the bus is (e.g., "Stopped at Main St") and how many stops away it is.
- Dynamic Train Syncing: Only recommends a bus if it actually arrives in time to catch the train.

## Setup

**Install Dependencies:**

`pip install requests iso8601`

**Add Your API Key:**  
Open commute_optimizer.py and insert your MBTA V3 API key in the run_loop() function:

`optimizer = CommuteOptimizer(api_key="your_key_here")`

**Run the Dashboard:**  
`python commute_optimizer.py`

## Configuration

You can customize your walk speeds and safety buffers at the top of the CommuteOptimizer class:

WALK_TO_BUS_STOPS: Time (mins) to get to your nearest stop.

SAFETY_BUFFER: Extra time to ensure you don't see the bus driving away as you arrive.