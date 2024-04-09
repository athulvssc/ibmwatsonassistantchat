from flask import Flask, jsonify, request, send_file
import pandas as pd
import requests
import math
from io import StringIO
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Load pre-trained GPT-2 model and tokenizer
model = GPT2LMHeadModel.from_pretrained("gpt2")
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

def fetchData(vendor=None):
    # Fetching CSV data
    csv_url = 'https://github.com/athulvssc/GRD-data/raw/main/goodsReceiptData.csv'
    response = requests.get(csv_url)
    csv_data = response.text

    # Parse CSV data using pandas
    df = pd.read_csv(StringIO(csv_data))

    if vendor:
        # Filter data by vendor
        vendor_data = df[df['vendor'] == vendor]

        # Calculate lowest GR qty for the vendor
        lowest_gr_qty = vendor_data['GR qty'].min()

        # Calculate cost reduction values for each material
        vendor_data['costReductionValue'] = ((vendor_data['GR qty'] - lowest_gr_qty) * vendor_data['  Net price']).apply(math.floor)

        # Select relevant columns
        cost_reduction_data = vendor_data[['vendor', 'costReductionValue']]
        return cost_reduction_data
    else:
        # Group by vendor and sum GR values
        vendor_gr_values = df.groupby('vendor')['GR value'].sum()

        # Sort by GR value and get top 10 suppliers
        top_10_vendors = vendor_gr_values.sort_values(ascending=False).head(10)

        # Convert top suppliers data to DataFrame
        top_suppliers_df = pd.DataFrame({'Vendor': top_10_vendors.index, 'GR Value': top_10_vendors.values})

        top_suppliers_df['GR Value'] = top_suppliers_df['GR Value'].apply(math.floor)

        return top_suppliers_df
    

def generate_response(query):
    # Tokenize the input query
    input_ids = tokenizer.encode(query, return_tensors="pt")

    # Generate response using the pre-trained model
    output = model.generate(input_ids, max_length=100, num_return_sequences=1, early_stopping=True)
    
    # Decode and return the generated response
    response = tokenizer.decode(output[0], skip_special_tokens=True)
    return response

def extract_vendor_from_query(query):
    # Find the position of "for vendor" in the query
    pos = query.lower().find("vendor")
    
    if pos != -1:
        # Extract the vendor name after "for vendor"
        query_after_vendor = query[pos + len("vendor"):]
        # Extract vendor name until the end of the query or until encountering a space
        vendor = query_after_vendor.split()[0]
        return vendor
    else:
        return None

@app.route('/query', methods=['POST'])
def process_query():
    try:
        query = request.data.decode('utf-8').strip()  # Decode the plain text data and remove leading/trailing whitespace
        response = None
        
        # Intent recognition logic
        if any(keyword in query.lower() for keyword in ['top suppliers', 'top vendors', 'top 10 suppliers', 'top 10 vendors']):
            data = fetchData()
            response = data.to_dict(orient='records')
            if 'excel' in query.lower():
                # Export to Excel format
                filename = 'top_suppliers.xlsx'
                data.to_excel(filename, index=False)
                return send_file(filename, as_attachment=True)
        elif 'cost reduction' in query.lower():
            vendor = extract_vendor_from_query(query)
            if vendor:
                data = fetchData(vendor)
                response = data.to_dict(orient='records')
                if 'excel' in query.lower():
                    # Export to Excel format
                    filename = f'cost_reduction_{vendor}.xlsx'
                    data.to_excel(filename, index=False)
                    return send_file(filename, as_attachment=True)
            else:
                response = {'error': 'Unable to extract vendor from query.'}
        else:
            # Return error message for unrecognized query
            response = {'error': 'The query you entered is incorrect . Please provide a valid query.'}

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
