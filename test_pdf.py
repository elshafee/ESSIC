import sys
import os

# Ensure the flask directory is in the python path
sys.path.append(os.path.join(os.path.dirname(__file__), "flask"))

from services.pdf_converter import convert_docx_to_pdf

input_docx = os.path.abspath("flask/template_essic.docx")
output_pdf = os.path.abspath("flask/test_output.pdf")

print(f"Converting {input_docx} to {output_pdf}...")
success = convert_docx_to_pdf(input_docx, output_pdf)

if success:
    print(f"SUCCESS! Output exists: {os.path.exists(output_pdf)}")
else:
    print("FAILED to convert.")
