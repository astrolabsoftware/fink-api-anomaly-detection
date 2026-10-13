# Notebooks for data exploring, analysis and modeling methodology

In the notebooks in this folder, we aim to explore the data, perform analyses, detect useful patterns, identify one or more baselines, and finally demonstrate model training and evaluation.

## Use a venv with Jupyter Notebook - Quick Steps

1. **Create a venv**
   ```bash
   python -m venv venv
   ```

2. **Activate the venv**
   - Linux/Mac: `source venv/bin/activate`
   - Windows: `.\venv\Scripts\activate`

3. **Install `requirements.txt`**
   ```bash
   pip install -r requirements.txt
   ```

4. **Register the kernel**
   ```bash
   python -m ipykernel install --user --name=vebv --display-name="venv"
   ```

5. **Select the kernel in Jupyter**
   - Open your `.ipynb` notebook
   - Go to **Kernel > Change kernel** and select `venv`

