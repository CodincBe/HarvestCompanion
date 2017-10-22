# Harvest Companion

A simple single-use tool to be able to use Harvest with decent time tracking while allowing the possibility of a fixed amount of billable hours in a day.

### Warning
This code was written a long time ago and quickly updated to work with python version 2.7.14.
This tool is presented as is and should be used with a sense of caution, while running successfully for a couple of years I might have not foreseen exceptional cases.

This tool expects a `config.ini` to be located in the same directory, based on the `config.ini.dist`.

### Options

For verbosity I have opted to have the project and task being listed as an option instead of an argument.
Be aware that those are required options.
 - **--days:** [default:0] The amount of days to correct relative to today (0 is today, 6 is an entire week)
 - **--project:** [mandatory] The id of the project you want to auto correct.
 - **--excess-task:** [mandatory] The id of the task where the excess of hours need to be registered.
 - **--max-hours:** [default:8] The max amount of hours that are billable in a day
 
## Issues & Contributions
I will keep an eye out for this repository but was written for my specific use case. In case you have issues feel free to open one.
Contributions are welcomed. 