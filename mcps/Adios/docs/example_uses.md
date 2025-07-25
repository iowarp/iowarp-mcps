## User examples 

### On wrp_chat Interface

**All the tools**

1. To List all the bp5 files in a directory. [Args: directorypath]

- prompt: list the files at Adios/data
- Answer: [
  "Adios/data/data3.bp",
  "Adios/data/data1.bp",
  "Adios/data/data2.bp"
]

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/list_files.png)

2. To Inspect all variables in a BP5 file (type, shape, available steps)  [Args: filename].

- prompt: how many steps do we have in Adios/data/data2.bp
- Answer: 
Output: {
  "greeting": {
    "AvailableStepsCount": "1",
    "Shape": "",
    "SingleValue": "true",
    "Type": "string"
  }
}

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/steps.png) 

3. To Read global or variable-specific attributes from a BP5 file. [Args: filename, optional: variable_name].

- prompt: inspect the attributes from variable pressure in Adios/data/data1.bp
- Answer: 
Output: {
  "unit": {
    "value": [
      "Pa"
    ],
    "Type": "string",
    "Elements": "1"
  }
}

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/attributes.png)  

4. To Read a named variable at a specific step from a BP5 file.  [Args: filename, variable_name, target_step].

- prompt: Read the value of variable physical_time at step 4 in Adios/data/data1.bp
- Answer: 
Output: {
  "value": 0.04
}

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/read_steps.png)

5. Reads all the variables/data and their steps from a BP5 file. [Args: filename].

- prompt: Read bp file at Adios/data/data3.bp
- Answer: 
Output: {
  "Nx": {
    "Step:0": 10
  },
  "bpArray": {
    "Step:0": [
      0.0,
      1.0,
      2.0,
      3.0,
      4.0,
      5.0,
      6.0,
      7.0,
      8.0,
      9.0
    ]
  }
}

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/read_bp5.png)

6. To Get minimum and maximum of a variable in a BP5 file. [Args: filename, variable_name, optional: step].

- prompt: Get the minimum value of variable physical_time from Adios/data/data1.bp
- Answer: 
Output: {
  "min": 0.0,
  "max": 0.04
}

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/minmax.png)

7. To add/Sum two variables in a BP5 file, either globally or at specific steps. [Args: filename, var1, var2, optional: step1, step2]

* Note: when doing the add operation make sure the shape of both of the variables is same or else it will throw an shapeerror.

- prompt: Add the value of variable physical_time at step 2 and variable nproc at step 0 in Adios/data/data1.bp
- Answer: 
Output: {
  "sum": 2.02
}

Sample:
![](https://github.com/iowarp/scientific-mcps/blob/main/Adios/assets/add_variables.png)