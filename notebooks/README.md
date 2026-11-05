## Setup - Quick Steps to use a venv with Jupyter Notebook

1. **Create a venv**
   ```bash
   python -m venv venv
   ```

2. **Activate the venv**
   - Linux/Mac: `source venv/bin/activate`
   - Windows: `.\venv\Scripts\activate`

3. **Install `requirements.txt`**
   ```bash
   pip install -r ../requirements.txt
   ```

4. **Register the kernel**
   ```bash
   python -m ipykernel install --user --name=venv --display-name="venv"
   ```

5. **Select the kernel in Jupyter**
   - Open your `.ipynb` notebook
   - Go to **Kernel > Change kernel** and select `venv`

You can therefore look toward [ztf/](ztf/README.md) for models trained on ZTF/Fink API logs or [lsst](lsst/README.md) (likewise).