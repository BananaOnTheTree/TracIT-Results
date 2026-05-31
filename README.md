# TracIT Coverage Artifacts

This repository contains artifacts for the paper "Trace-Driven Large Language Model Test Generation for High-Coverage C++ Unit Testing"

First, unzip all the files to restore the original directory structure inside the [results file](results.rar).

Repository layout

- `results/`: Contains logs of LLM outputs for tested focal methods. 
Structure of the folder:
    - `Method`: Name of the approach used for test generation.
        - `Project`: Name of the C++ project
            - `FocalMethod`: Name of the focal method being tested.
                - `focal_method_ai_#Number_logs.json`: The trace logs for each LLM test run.
                - `coverage_focal_method.json`: Final coverage result for the focal method.

- [Output](output): Contains tables and figures used in the paper, generated from the results in the `results/` folder and the scripts.

