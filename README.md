# 📚 Hệ Thống Quản Lý Thư Viện Thông Minh (Oracle & Neo4j)

Ứng dụng quản lý thư viện hiện đại tích hợp sức mạnh của cơ sở dữ liệu quan hệ (**Oracle**) và cơ sở dữ liệu đồ thị (**Neo4j**), giúp quản lý giao dịch mượn trả và cung cấp tính năng gợi ý sách thông minh.

## ✨ Tính năng chính
- **Quản lý dữ liệu (Oracle):** Lưu trữ và truy xuất thông tin chi tiết về Sách, Tác giả, Người dùng và các giao dịch Phiếu mượn.
- **Gợi ý thông minh (Neo4j):** Phân tích mối quan hệ giữa các nút (Nodes) để đưa ra gợi ý sách dựa trên thể loại hoặc tác giả tương tự.
- **Giao diện trực quan:** Sử dụng **Streamlit** để hiển thị dashboard báo cáo, tìm kiếm và quản lý dữ liệu thời gian thực.

## 🛠 Yêu cầu hệ thống
- **Ngôn ngữ:** Python 3.x
- **Cơ sở dữ liệu:** - Oracle Database (Quản lý dữ liệu có cấu trúc)
  - Neo4j Graph Database (Xử lý mối quan hệ và gợi ý)
***
# 🚀 Sử dụng

## Cài đặt các thư viện cần thiết:
```pip install -r requirements.txt``` 

## Sao chép file .env.example thành file .env và điền thông tin kết nối database của bạn

## Khởi chạy ứng dụng:
```streamlit run app.py```
Hoặc
```python -m streamlit run app.py```
