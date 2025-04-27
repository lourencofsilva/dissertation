# Project Overview

A comprehensive predictive model training, simulation and benchmarking tool designed to analyze and visualize traffic data and congestion using predictive models. It leverages Python for data processing, SUMO for traffic simulation, and InfluxDB for data storage and retrieval. This project is developed as part of a 3rd Year Project.

## Report

The report produced for this project can be found here: [Project Report (PDF)](report/pdf/report.pdf)

## Screencast

The screencast produced for this project can be found here: [Screencast (MP4)](screencast/screencast.mp4)

## Requirements

1. **Python Virtual Environment**:
   - Create a virtual environment and install the required packages:
     ```bash
     python -m venv venv
     source venv/bin/activate
     pip install -r requirements.txt
     ```

2. **SUMO**:
   - Ensure that SUMO (Simulation of Urban MObility) is installed and properly configured on your system. You can download it from [SUMO's official website](https://eclipse.dev/sumo/).

3. **InfluxDB**:
   - You can set up InfluxDB either on a server or locally. The scripts with which data was collected are available in the `data-sources` directory.

4. **Configuration**:
   - Fill in the required keys and configuration in `tools/config.py`.

## Directory Structure

### `benchmarking/`
This directory includes benchmarking data generated from the development and research effort of the project.

### `data-analysis/`
This directory contains a jupyter notebook for data analysis and visualization of the collected traffic data.

### `data-sources/`
This directory contains scripts for collecting traffic and event data from various sources.

### `model/`
This directory contains a framework for training predictive models for traffic sensors. Key files include:
- `batch_training.py`: Trains multiple models for different sensors in a batch.
- `train_model_nn.py`: Trains a neural network model (MLP) for a single sensor.
- `predict.py`: Generates predictions using the trained models.
- `model_training.py`: Contains the model architectures and training logic.
- `data_loader.py`: Contains the data loader for the models.
- `create-estimations.py`: Uses LLMs to estimate attendance at events.
- `feature_engineering.py`: Contains the feature engineering logic created for event, weather, and traffic data features.

### `simulations/`
This directory contains scripts and tools for running traffic simulations using SUMO on real-world data. Key files include:
- `plot_metrics.py`: Generates plots and aggregated metrics for simulation runs.
- `run_simu.py`: Runs traffic simulations using SUMO and TRACI across multiple scenarios and control strategies using VSL.
- `add_sensors.py` and `generate_demand.py`: Converts a base simulation into one from real-world data by generating demand and adding sensors as per collected data.

### `tools/`
This directory contains utility scripts and configuration files.
- `config.py`: Configuration file where you need to fill in the required keys and settings.

## Running the Project

1. **Set Up the Environment**:
   - Create and activate the Python virtual environment.
   - Install the required packages using `requirements.txt`.

2. **Configure SUMO**:
   - Ensure SUMO is installed and configured correctly.

3. **Set Up InfluxDB**:
   - Set up the database and perform data collection.

4. **Configure the Project**:
   - Fill in the necessary configuration in `tools/config.py`.

5. **Train Required Models**:
   - Use `train_model_nn.py` or `batch_training.py` to train predictive models for the required sensors.

6. **Generate Predictions**:
   - Use `predict.py` to generate predictions using the trained models.

7. **Run Simulations**:
   - Use the `add_sensors.py` and `generate_demand.py` scripts with the `base-sim` folder to generate demand for a particular day.
   - Run the simulation using `run_simu.py`.

8. **Plot Metrics**:
   - Use `plot_metrics.py` to aggregate and generate plots for simulation metrics.

## Author
Lourenço Figueiredo Silva (<lourenco.figueiredosilva@student.manchester.ac.uk>)

Supervised by: Dr. Sandra Sampaio (s.sampaio@manchester.ac.uk)

