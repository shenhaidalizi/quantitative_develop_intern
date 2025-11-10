from test_generate import generate_fake_stock_data, load_stock_basic_info

def fake_data_source(batch_index=0, batch_size=100):
    stock_basic_info = load_stock_basic_info("data/stock_basic_info.json")['data']
    fixed_stock_info = stock_basic_info[:batch_size]
    return generate_fake_stock_data(fixed_stock_info)
