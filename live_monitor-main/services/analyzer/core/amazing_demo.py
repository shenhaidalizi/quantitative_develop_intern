# 第一步 登录api 
import AmazingData as ad 
import dotenv
import os
dotenv.load_dotenv()
username = os.getenv("AMZ_USERNAME")
password = os.getenv("AMZ_PWD")
host = os.getenv("AMZ_HOST")
port = int(os.getenv("AMZ_PORT"))

ad.login(username, password,host,port) 
base_data_object = ad.BaseData() 
code_list = base_data_object.get_code_list(security_type=' EXTRA_INDEX_A ') 

# 实时订阅 
sub_data = ad.SubscribeData() 
@sub_data.register(code_list=code_list, period=ad.constant.Period.snapshot.value) 
def onSnapshot(index: Union[ad.constant.Snapshot, ad.constant.SnapshotIndex], period):     
    print(period, data)  
sub_data.run()    