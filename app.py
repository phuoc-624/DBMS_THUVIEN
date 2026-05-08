import os
import streamlit as st
import oracledb
from dotenv import load_dotenv
from neo4j import GraphDatabase
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()

# --- 1. CẤU HÌNH KẾT NỐI ---
oracle_config = {
    "user": os.getenv("ORACLE_USER"),
    "password": os.getenv("ORACLE_PASSWORD"),
    "dsn": os.getenv("ORACLE_DSN")
}

neo4j_uri = os.getenv("NEO4J_URI")
neo4j_auth = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
ADMIN_SECRET_KEY = "BK_LIBRARY_2026" 

# --- 2. HÀM LOGIC BACKEND ---
@st.cache_resource
def get_neo4j_driver():
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        # Kiểm tra kết nối
        driver.verify_connectivity()
        return driver
    except Exception as e:
        st.error(f"❌ Không thể kết nối đến Neo4j: {e}")
        return None

# 3. Hàm thực thi câu lệnh Cypher (Tương tự execute_oracle)
def execute_neo4j(cypher_query, parameters=None):
    """
    Thực thi câu lệnh Cypher và trả về kết quả dưới dạng danh sách các Dictionary.
    - cypher_query: Chuỗi truy vấn Cypher.
    - parameters: Dictionary chứa các tham số (ví dụ: {"ma_dg": "DG001"}).
    Trả về: (dữ_liệu_list, lỗi_nếu_có)
    """
    driver = get_neo4j_driver()
    if not driver:
        return None, "Neo4j Driver không hoạt động."
        
    data = []
    error = None
    
    # Đảm bảo parameters là dictionary (nếu rỗng thì gán bằng dict rỗng)
    if parameters is None:
        parameters = {}
        
    try:
        # Mở một session để giao tiếp với DB
        with driver.session() as session:
            # Chạy lệnh
            result = session.run(cypher_query, parameters)
            
            # Đọc từng dòng kết quả và ép kiểu về dạng Dictionary của Python
            for record in result:
                data.append(dict(record))
                
    except Exception as e:
        error = str(e)
        
    return data, error

def execute_oracle(sql, params=None, is_select=True):
    try:
        conn = oracledb.connect(**oracle_config)
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        if is_select:
            result = cursor.fetchall()
            cols = [col[0] for col in cursor.description] if cursor.description else []
            cursor.close()
            conn.close()
            return result, cols
        else:
            conn.commit()
            cursor.close()
            conn.close()
            return True, None
    except Exception as e:
        return None, str(e)

def get_or_create_metadata(table_name, id_prefix, name_val):
    id_col = "MA_THE_LOAI" if table_name == "THE_LOAI" else "MA_TG"
    name_col = "TEN_THE_LOAI" if table_name == "THE_LOAI" else "TEN_TG"
    sql_check = f"SELECT {id_col} FROM {table_name} WHERE UPPER({name_col}) = UPPER(:1)"
    res, _ = execute_oracle(sql_check, [name_val.strip()])
    if res:
        return res[0][0]
    else:
        new_id = get_next_id(table_name, id_col, id_prefix)
        #new_id = get_next_ma_the_loai() if id_prefix == "TL" else get_next_ma_tg()
        #new_id = f"{id_prefix}{random.randint(1000, 9999)}"
        sql_insert = f"INSERT INTO {table_name} ({id_col}, {name_col}) VALUES (:1, :2)"
        execute_oracle(sql_insert, [new_id, name_val.strip()], is_select=False)
        return new_id

def get_next_id(table, col, prefix):
    sql = f"SELECT MAX({col}) FROM {table}"
    res, _ = execute_oracle(sql)
    if res and res[0][0]:
        current_max = res[0][0]
        number_part = int(current_max[len(prefix):])
        return f"{prefix}{number_part + 1:03d}"
    return f"{prefix}001"


def display_recommendations():
    st.subheader("💡 Sách có thể bạn sẽ thích")
    ma_dg = st.session_state.user_id
    
    # if not ma_dg:
    #     st.info("Đăng nhập để xem gợi ý cá nhân hóa.")
    #     return

    # Bước 1: Tìm ID sách từ Neo4j
    cypher_query = """
    MATCH (me:User {id: $ma_dg})-[:BORROWED]->(b:Book)<-[:BORROWED]-(other:User)-[:BORROWED]->(rec:Book)
    WHERE NOT (me)-[:BORROWED]->(rec)
    RETURN rec.id AS ma_sach, COUNT(DISTINCT other) AS score
    ORDER BY score DESC LIMIT 5
    """
    data_neo, error = execute_neo4j(cypher_query, {"ma_dg": ma_dg})

    if error or not data_neo:
        st.caption("Chưa có gợi ý nào dựa trên lịch sử mượn. Hãy xem các sách mới nhất bên dưới!")
        return

    # Bước 2: Lấy danh sách ID để truy vấn Oracle
    list_ma_sach = [f"'{item['ma_sach']}'" for item in data_neo]
    where_clause = f"S.MA_SACH IN ({', '.join(list_ma_sach)})"

    # Truy vấn lấy đầy đủ 6 cột dữ liệu như hàm display_book_grid yêu cầu
    sql_query = f"""
        SELECT S.MA_SACH, S.TEN_SACH, TL.TEN_THE_LOAI, 
               (SELECT LISTAGG(TG.TEN_TG, ', ') WITHIN GROUP (ORDER BY TG.TEN_TG) 
                FROM TAC_GIA TG JOIN SACH_TAC_GIA STG ON TG.MA_TG = STG.MA_TG 
                WHERE STG.MA_SACH = S.MA_SACH) as TAC_GIA,
               S.NAM_XB, S.SO_LUONG
        FROM SACH S
        JOIN THE_LOAI TL ON S.MA_THE_LOAI = TL.MA_THE_LOAI
        WHERE {where_clause}
    """
    
    res_oracle, err_oracle = execute_oracle(sql_query)

    if res_oracle:
        # Bước 3: Gọi hàm grid của bạn với prefix "rec" để tránh trùng key nút bấm
        display_book_grid(res_oracle, prefix="rec")
    else:
        st.warning("Không tìm thấy chi tiết sách gợi ý trong hệ thống.")

def display_user_management(search_term=None):
    # 1. Thanh công cụ lọc trạng thái
    col_search, col_filter = st.columns([3, 1])
    with col_filter:
        status_option = st.selectbox(
            "Lọc trạng thái",
            options=["Tất cả", "Hoạt động", "Đã khóa"],
            index=0
        )

    # 2. Xây dựng câu lệnh SQL
    sql = "SELECT MA_DG, USERNAME, HO_TEN, SO_DIEN_THOAI, TRANG_THAI FROM NGUOI_DUNG WHERE 1=1"
    params = []

    # Lọc theo trạng thái
    if status_option == "Hoạt động":
        sql += " AND TRANG_THAI = 1"
    elif status_option == "Đã khóa":
        sql += " AND TRANG_THAI = 0"

    # Lọc theo từ khóa (Thêm USERNAME vào đây)
    if search_term:
        # Tăng số lượng tham số lên 4 (Ho_ten, SDT, Ma_dg, Username)
        sql += """ AND (
            UPPER(HO_TEN) LIKE UPPER(:1) 
            OR SO_DIEN_THOAI LIKE :2 
            OR MA_DG = :3 
            OR UPPER(USERNAME) LIKE UPPER(:4)
        )"""
        search_val = f"%{search_term}%"
        params = [search_val, search_val, search_term, search_val]
    
    data, _ = execute_oracle(sql, params)
    
    # 3. Hiển thị giao diện bảng
    if data:
        cols = st.columns([1, 1.5, 2, 1.5, 1.2, 1.2])
        headers = ["Mã ĐG", "Username", "Họ Tên", "SĐT", "Trạng Thái", "Thao tác"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")
        
        st.divider()

        for row in data:
            ma_dg, username, ho_ten, sdt, trang_thai = row
            c1, c2, c3, c4, c5, c6 = st.columns([1, 1.5, 2, 1.5, 1.2, 1.2])
            
            c1.text(ma_dg)
            c2.text(username)
            c3.text(ho_ten)
            c4.text(sdt)
            
            status_label = "🟢 Hoạt động" if trang_thai == 1 else "🔴 Đã khóa"
            c5.write(status_label)
            
            btn_label = "Khóa" if trang_thai == 1 else "Mở khóa"
            if c6.button(btn_label, key=f"btn_{ma_dg}", use_container_width=True, 
                         type="secondary" if trang_thai == 1 else "primary"):
                
                new_status = 0 if trang_thai == 1 else 1
                update_sql = "UPDATE NGUOI_DUNG SET TRANG_THAI = :1 WHERE MA_DG = :2"
                execute_oracle(update_sql, [new_status, ma_dg], is_select=False)
                
                st.toast(f"Đã cập nhật trạng thái cho {username}!")
                st.rerun()
    else:
        st.info("Không tìm thấy tài khoản phù hợp.")

def display_user_borrow_history():
    st.subheader("📖 Lịch sử mượn sách của bạn")
    
    # Lấy ID người dùng đang đăng nhập từ session_state
    ma_dg = st.session_state.get("user_id") 
    
    if not ma_dg:
        st.warning("Vui lòng đăng nhập để xem lịch sử.")
        return

    # 1. Bộ lọc dành riêng cho User
    with st.expander("🔍 Tìm kiếm trong lịch sử của bạn", expanded=True):
        f1, f2 = st.columns([2, 1])
        search_book = f1.text_input("Nhập tên sách cần tìm")
        status_filter = f2.selectbox("Trạng thái", ["Tất cả", "Đang mượn", "Đã trả"], index=0)

        f3, f4 = st.columns(2)
        # Sử dụng lọc chính xác một ngày (không dùng khoảng)
        date_m = f3.date_input("Lọc theo ngày mượn", value=None)
        date_h = f4.date_input("Lọc theo hạn trả dự kiến", value=None)

    # 2. Xây dựng SQL (Luôn luôn lọc theo MA_DG của user hiện tại)
    sql = """
        SELECT pm.MA_PM, s.TEN_SACH, pm.SO_LUONG_MUON, 
               pm.NGAY_MUON, pm.NGAY_TRA_DU_KIEN, pm.TRANG_THAI
        FROM PHIEU_MUON pm
        JOIN SACH s ON pm.MA_SACH = s.MA_SACH
        WHERE pm.MA_DG = :1
    """
    params = [ma_dg]

    if search_book:
        sql += f" AND UPPER(s.TEN_SACH) LIKE UPPER(:{len(params)+1})"
        params.append(f"%{search_book}%")

    if status_filter != "Tất cả":
        sql += f" AND pm.TRANG_THAI = :{len(params)+1}"
        params.append(status_filter)

    # Sửa lỗi lọc ngày bằng TRUNC để bỏ qua giờ/phút/giây
    if date_m:
        sql += f" AND TRUNC(pm.NGAY_MUON) = :{len(params)+1}"
        params.append(date_m)
        
    if date_h:
        sql += f" AND TRUNC(pm.NGAY_TRA_DU_KIEN) = :{len(params)+1}"
        params.append(date_h)

    sql += " ORDER BY pm.NGAY_MUON DESC" # Sách mới mượn hiện lên đầu
    
    data, _ = execute_oracle(sql, params)

    # 3. Hiển thị Grid kết quả
    if data:
        st.write(f"Bạn có **{len(data)}** bản ghi mượn sách.")
        cols = st.columns([1, 2, 0.8, 1.2, 1.2, 1])
        headers = ["Mã PM", "Tên Sách", "SL", "Ngày Mượn", "Hạn Trả", "Trạng Thái"]
        for col, h in zip(cols, headers): col.markdown(f"**{h}**")
        st.divider()

        for row in data:
            ma_pm, ten_sach, sl_muon, ngay_m, ngay_h, status = row
            c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 0.8, 1.2, 1.2, 1])
            
            c1.text(ma_pm)
            c2.text(ten_sach)
            c3.text(sl_muon)
            c4.text(ngay_m.strftime('%d/%m/%Y'))
            
            # Kiểm tra quá hạn để đổi màu cho User biết
            is_overdue = ngay_h < datetime.now() and status == 'Đang mượn'
            h_color = "red" if is_overdue else "black"
            c5.markdown(f"<span style='color:{h_color}'>{ngay_h.strftime('%d/%m/%Y')}</span>", unsafe_allow_html=True)
            
            st_icon = "🔵" if status == "Đang mượn" else "🟢"
            c6.text(f"{st_icon} {status}")
    else:
        st.info("Lịch sử trống. Hãy mượn cuốn sách đầu tiên của bạn nhé!")

def borrow_book_page():
    st.button("⬅️ Quay lại danh sách", on_click=lambda: st.session_state.update(page="catalog"))
    
    st.header("📝 Phiếu Đăng Ký Mượn Sách")
    
    ma_sach = st.session_state.borrow_book_id
    ten_sach = st.session_state.borrow_book_name
    ton_kho = st.session_state.borrow_book_stock
    ma_dg = st.session_state.user_id # Giả sử bạn đã lưu user_id khi đăng nhập
    
    st.info(f"**Độc giả:** {st.session_state.user_name} | **Mã ĐG:** {ma_dg}")
    
    # Hiển thị thông tin sách đang mượn
    st.markdown(f"### 📘 {ten_sach} (Mã: {ma_sach})")
    st.write(f"Số lượng hiện có trong thư viện: **{ton_kho}** quyển")
    
    # Form điền thông tin mượn
    with st.form("borrow_form"):
        # 1. Nhập số lượng
        so_luong_muon = st.number_input("Số lượng mượn", min_value=1, value=1, step=1)
        
        # 2. Chọn thời hạn mượn
        thoi_han = st.selectbox("Thời hạn mượn", ["3 ngày", "1 tuần", "Tối đa 2 tuần (14 ngày)"])
        
        # Tính toán ngày thực tế
        ngay_muon = datetime.now()
        if thoi_han == "3 ngày":
            so_ngay = 3
        elif thoi_han == "1 tuần":
            so_ngay = 7
        else:
            so_ngay = 14
            
        ngay_tra_du_kien = ngay_muon + timedelta(days=so_ngay)
        
        st.write(f"**Ngày mượn:** {ngay_muon.strftime('%d/%m/%Y')}")
        st.write(f"**Ngày trả dự kiến:** {ngay_tra_du_kien.strftime('%d/%m/%Y')}")
        
        submit = st.form_submit_button("Xác nhận mượn sách", type="primary")
        
        if submit:
            if so_luong_muon > ton_kho:
                st.error(f"❌ Thư viện không đủ số lượng! Chỉ còn {ton_kho} quyển.")
            else:
                try:
                    # BƯỚC MỚI: Tự động lấy mã phiếu mượn tiếp theo (ví dụ: PM001, PM002...)
                    ma_pm_moi = get_next_id("PHIEU_MUON", "MA_PM", "PM")
                    
                    # 1. Câu lệnh INSERT đã có đầy đủ MA_PM
                    sql_phieu = """
                        INSERT INTO PHIEU_MUON (MA_PM, MA_DG, MA_SACH, NGAY_MUON, SO_LUONG_MUON, NGAY_TRA_DU_KIEN, TRANG_THAI) 
                        VALUES (:1, :2, :3, SYSDATE, :4, SYSDATE + :5, 'Đang mượn')
                    """
                    
                    # Chạy lệnh INSERT - Truyền ma_pm_moi vào tham số :1
                    success_p, err_p = execute_oracle(sql_phieu, [ma_pm_moi, ma_dg, ma_sach, so_luong_muon, so_ngay], is_select=False)
                    
                    if success_p:
                        # 2. Cập nhật kho sách
                        sql_update_stock = "UPDATE SACH SET SO_LUONG = SO_LUONG - :1 WHERE MA_SACH = :2"
                        success_s, err_s = execute_oracle(sql_update_stock, [so_luong_muon, ma_sach], is_select=False)
                        
                        if success_s:
                            st.success(f"🎉 Mượn sách thành công! Mã phiếu của bạn là: **{ma_pm_moi}**")
                            st.session_state.borrow_book_stock -= so_luong_muon
                        else:
                            st.error(f"Lỗi cập nhật kho: {err_s}")
                    else:
                        st.error(f"Lỗi tạo phiếu mượn: {err_p}")
                        
                except Exception as e:
                    st.error(f"Lỗi hệ thống: {e}")

def display_borrow_management():
    st.subheader("📋 Quản lý Mượn/Trả sách")
    
    # 1. Khu vực Bộ lọc (Filters)
    with st.expander("🔍 Bộ lọc tìm kiếm", expanded=True):
        f1, f2, f3 = st.columns([2, 1, 1.2])
        search_kw = f1.text_input("Tìm theo Tên Độc giả hoặc Tên Sách")
        
        status_options = ["Tất cả", "Đang mượn", "Đã trả"]
        status_filter = f2.selectbox("Trạng thái", options=status_options, index=1)
        
        overdue_filter = f3.checkbox("⚠️ Chỉ hiện sách quá hạn")

        f4, f5 = st.columns(2)
        # Thay đổi: Sử dụng value=None để lọc theo ngày cụ thể, không dùng khoảng (range)
        date_m = f4.date_input("Lọc chính xác Ngày mượn", value=None)
        date_h = f5.date_input("Lọc chính xác Hạn trả", value=None)

    # 2. Xây dựng câu lệnh SQL
    sql = """
        SELECT pm.MA_PM, nd.MA_DG, nd.HO_TEN, s.TEN_SACH, pm.SO_LUONG_MUON,
               pm.NGAY_MUON, pm.NGAY_TRA_DU_KIEN, pm.TRANG_THAI, s.MA_SACH
        FROM PHIEU_MUON pm
        JOIN NGUOI_DUNG nd ON pm.MA_DG = nd.MA_DG
        JOIN SACH s ON pm.MA_SACH = s.MA_SACH
        WHERE pm.TRANG_THAI != 'Chờ duyệt'
    """
    params = []

    # ... (Giữ nguyên các phần lọc Search và Status) ...
    if search_kw:
        sql += " AND (UPPER(nd.HO_TEN) LIKE UPPER(:1) OR UPPER(s.TEN_SACH) LIKE UPPER(:2) OR nd.MA_DG = :3)"
        params += [f"%{search_kw}%", f"%{search_kw}%", search_kw]

    if status_filter != "Tất cả":
        sql += f" AND pm.TRANG_THAI = :{len(params)+1}"
        params.append(status_filter)

    if overdue_filter:
        sql += " AND pm.NGAY_TRA_DU_KIEN < SYSDATE AND pm.TRANG_THAI = 'Đang mượn'"

    # SỬA ĐỔI: Lọc ngày chính xác bằng TRUNC để bỏ qua giờ phút giây
    if date_m:
        sql += f" AND TRUNC(pm.NGAY_MUON) = :{len(params)+1}"
        params.append(date_m)

    if date_h:
        sql += f" AND TRUNC(pm.NGAY_TRA_DU_KIEN) = :{len(params)+1}"
        params.append(date_h)

    sql += " ORDER BY pm.NGAY_TRA_DU_KIEN ASC"
    
    data, _ = execute_oracle(sql, params)
    
    # 3. Hiển thị kết quả
    if data:
        st.write(f"Tìm thấy **{len(data)}** bản ghi.")
        cols = st.columns([0.7, 1.2, 1.2, 0.5, 1, 1, 0.8, 1])
        headers = ["Mã PM", "Độc Giả", "Tên Sách", "SL", "Ngày Mượn", "Hạn Trả", "Trạng Thái", "Thao tác"]
        for col, h in zip(cols, headers): col.markdown(f"**{h}**")
        st.divider()

        for row in data:
            ma_pm, ma_dg, ho_ten, ten_sach, so_luong_muon, ngay_m, ngay_h, status, ma_sach = row
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([0.7, 1.2, 1.2, 0.5, 1, 1, 0.8, 1])
            
            c1.text(ma_pm)
            c2.text(f"{ho_ten}\n({ma_dg})")
            c3.text(ten_sach)
            c4.text(so_luong_muon)
            c5.text(ngay_m.strftime('%d/%m/%Y'))
            
            # Highlight quá hạn
            is_overdue = ngay_h < datetime.now() and status == 'Đang mượn'
            h_color = "red" if is_overdue else "black"
            c6.markdown(f"<span style='color:{h_color}'>{ngay_h.strftime('%d/%m/%Y')}</span>", unsafe_allow_html=True)
            
            # Label trạng thái
            st_icon = "🔵" if status == "Đang mượn" else "🟢"
            c7.text(f"{st_icon} {status}")
            
            # Nút xác nhận trả sách
            if status == 'Đang mượn':
                if c8.button("📥 Trả sách", key=f"ret_{ma_pm}", use_container_width=True):
                    confirm_return(ma_pm, ma_dg, ma_sach)
            else:
                c8.write("✅ Đã hoàn thành")
    else:
        st.info("Không có dữ liệu mượn trả phù hợp với bộ lọc.")

def confirm_return(ma_pm, ma_dg, ma_sach):
    # 1. Cập nhật trạng thái phiếu mượn
    sql1 = "UPDATE PHIEU_MUON SET TRANG_THAI = 'Đã trả', NGAY_TRA_THUC_TE = SYSDATE WHERE MA_PM = :1"
    # 2. Cộng lại số lượng vào kho sách
    #sql2 = "UPDATE SACH SET SO_LUONG = SO_LUONG + 1 WHERE MA_SACH = :1"
    sql2 = "UPDATE SACH SET SO_LUONG = SO_LUONG + (SELECT SO_LUONG_MUON FROM PHIEU_MUON WHERE MA_PM = :1) WHERE MA_SACH = :2"
    # 3. Mở khóa tài khoản user (Trạng thái = 1)
    sql3 = "UPDATE NGUOI_DUNG SET TRANG_THAI = 1 WHERE MA_DG = :1"
    
    execute_oracle(sql1, [ma_pm], is_select=False)
    execute_oracle(sql2, [ma_pm, ma_sach], is_select=False)
    execute_oracle(sql3, [ma_dg], is_select=False)
    
    st.success(f"Đã xử lý trả sách cho phiếu {ma_pm}. Tài khoản {ma_dg} đã được mở khóa.")
    st.rerun()

def display_comprehensive_catalog_user():
    st.subheader("📋 Danh mục sách chi tiết (Oracle)")
    
    # Query Join 4 bảng với LISTAGG và thêm cột SO_LUONG
    # Lưu ý: Phải thêm s.SO_LUONG vào GROUP BY để tránh lỗi SQL
    sql_query = """
        SELECT 
            s.MA_SACH, 
            s.TEN_SACH, 
            t.TEN_THE_LOAI, 
            LISTAGG(tg.TEN_TG, ', ') WITHIN GROUP (ORDER BY tg.TEN_TG) AS TAC_GIA,
            s.NAM_XB,
            s.SO_LUONG
        FROM SACH s
        JOIN THE_LOAI t ON s.MA_THE_LOAI = t.MA_THE_LOAI
        LEFT JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
        LEFT JOIN TAC_GIA tg ON stg.MA_TG = tg.MA_TG
        GROUP BY s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, s.NAM_XB, s.SO_LUONG
        ORDER BY s.MA_SACH
    """
    
    data, cols = execute_oracle(sql_query)
    
    if data:
        # Thêm cột "Số Lượng" vào danh sách cột của DataFrame
        #df = pd.DataFrame(data, columns=["Mã Sách", "Tên Sách", "Thể Loại", "Tác Giả", "Năm XB", "Số Lượng"])
        
        # Mẹo: Highlight màu đỏ nếu số lượng bằng 0 để Admin dễ nhận biết
        def highlight_out_of_stock(row):
            return ['color: red' if row['Số Lượng'] == 0 else '' for _ in row]
        display_book_grid(data)
    else:
        st.info("Thư viện hiện đang trống.")

def display_comprehensive_catalog():
    st.subheader("📋 Danh mục sách chi tiết (Oracle)")
    
    # Query Join 4 bảng với LISTAGG và thêm cột SO_LUONG
    # Lưu ý: Phải thêm s.SO_LUONG vào GROUP BY để tránh lỗi SQL
    sql_query = """
        SELECT 
            s.MA_SACH, 
            s.TEN_SACH, 
            t.TEN_THE_LOAI, 
            LISTAGG(tg.TEN_TG, ', ') WITHIN GROUP (ORDER BY tg.TEN_TG) AS TAC_GIA,
            s.NAM_XB,
            s.SO_LUONG
        FROM SACH s
        JOIN THE_LOAI t ON s.MA_THE_LOAI = t.MA_THE_LOAI
        LEFT JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
        LEFT JOIN TAC_GIA tg ON stg.MA_TG = tg.MA_TG
        GROUP BY s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, s.NAM_XB, s.SO_LUONG
        ORDER BY s.MA_SACH
    """
    
    data, cols = execute_oracle(sql_query)
    
    if data:
        # Thêm cột "Số Lượng" vào danh sách cột của DataFrame
        df = pd.DataFrame(data, columns=["Mã Sách", "Tên Sách", "Thể Loại", "Tác Giả", "Năm XB", "Số Lượng"])
        
        # Mẹo: Highlight màu đỏ nếu số lượng bằng 0 để Admin dễ nhận biết
        def highlight_out_of_stock(row):
            return ['color: red' if row['Số Lượng'] == 0 else '' for _ in row]
        st.dataframe(
            df.style.apply(highlight_out_of_stock, axis=1), 
            width="stretch", 
            hide_index=True
        )
    else:
        st.info("Thư viện hiện đang trống.")

def search_books_advanced(ma_sach=None, ten_sach=None, nam_xb=None, the_loai=None, tac_gia=None, tinh_trang="Tất cả"):
    sql = """
        SELECT 
            s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, 
            LISTAGG(tg.TEN_TG, ', ') WITHIN GROUP (ORDER BY tg.TEN_TG) AS TAC_GIA,
            s.NAM_XB, s.SO_LUONG
        FROM SACH s
        JOIN THE_LOAI t ON s.MA_THE_LOAI = t.MA_THE_LOAI
        LEFT JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
        LEFT JOIN TAC_GIA tg ON stg.MA_TG = tg.MA_TG
        WHERE 1=1
    """
    params = []
    
    # ... (Các điều kiện cũ giữ nguyên) ...
    if ma_sach:
        sql += " AND s.MA_SACH = :1"
        params.append(ma_sach)
    if ten_sach:
        sql += " AND UPPER(s.TEN_SACH) LIKE UPPER(:2)"
        params.append(f"%{ten_sach}%")
    if nam_xb:
        sql += " AND s.NAM_XB = :3"
        params.append(nam_xb)
    if the_loai:
        sql += " AND UPPER(t.TEN_THE_LOAI) LIKE UPPER(:4)"
        params.append(f"%{the_loai}%")
    if tac_gia:
        sql += " AND UPPER(tg.TEN_TG) LIKE UPPER(:5)"
        params.append(f"%{tac_gia}%")

    # MỚI: Lọc theo số lượng (Tình trạng kho)
    if tinh_trang == "Còn hàng":
        sql += " AND s.SO_LUONG > 0"
    elif tinh_trang == "Hết hàng":
        sql += " AND s.SO_LUONG = 0"
        
    sql += " GROUP BY s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, s.NAM_XB, s.SO_LUONG"
    return execute_oracle(sql, params)

def search_logic():
    st.subheader("🔍 Bộ lọc tìm kiếm")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        ma = st.text_input("Mã sách", key="search_ma")
    with c2:
        ten = st.text_input("Tên sách", key="search_ten")
    with c3:
        nam_raw = st.text_input("Năm xuất bản", key="search_nam")
    
    c4, c5, c6 = st.columns(3) # Chia làm 3 cột để thêm ô Số lượng
    with c4:
        tl = st.text_input("Thể loại", key="search_tl")
    with c5:
        tg = st.text_input("Tác giả", key="search_tg")
    with c6:
        # Thay vì nhập số, ta chọn trạng thái kho sẽ tiện hơn cho Admin/User
        tinh_trang = st.selectbox("Tình trạng kho", ["Tất cả", "Còn hàng", "Hết hàng"])

    if st.button("Bắt đầu tìm", width="stretch"):
        # VALIDATION Năm
        valid = True
        n_val = None
        if nam_raw:
            try:
                n_val = int(nam_raw)
                if n_val < 0 or n_val > 2026:
                    st.error(f"❌ Năm '{nam_raw}' không hợp lệ (0-2026)")
                    valid = False
            except ValueError:
                st.error(f"❌ Năm phải là số nguyên!")
                valid = False

        if valid:
            res, _ = search_books_advanced(ma, ten, n_val, tl, tg, tinh_trang)
            if res:
                df = pd.DataFrame(res, columns=["Mã", "Tên Sách", "Thể Loại", "Tác Giả", "Năm", "Số Lượng"])
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.info("⚠️ Không tìm thấy kết quả phù hợp.")

def search_logic_user():
    st.subheader("🔍 Bộ lọc tìm kiếm")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        ma = st.text_input("Mã sách", key="search_ma")
    with c2:
        ten = st.text_input("Tên sách", key="search_ten")
    with c3:
        nam_raw = st.text_input("Năm xuất bản", key="search_nam")
    
    c4, c5, c6 = st.columns(3) # Chia làm 3 cột để thêm ô Số lượng
    with c4:
        tl = st.text_input("Thể loại", key="search_tl")
    with c5:
        tg = st.text_input("Tác giả", key="search_tg")
    with c6:
        # Thay vì nhập số, ta chọn trạng thái kho sẽ tiện hơn cho Admin/User
        tinh_trang = st.selectbox("Tình trạng kho", ["Tất cả", "Còn hàng", "Hết hàng"])

    if st.button("Bắt đầu tìm", width="stretch"):
        # VALIDATION Năm
        valid = True
        n_val = None
        if nam_raw:
            try:
                n_val = int(nam_raw)
                if n_val < 0 or n_val > 2026:
                    st.error(f"❌ Năm '{nam_raw}' không hợp lệ (0-2026)")
                    valid = False
            except ValueError:
                st.error(f"❌ Năm phải là số nguyên!")
                valid = False

        if valid:
            res, _ = search_books_advanced(ma, ten, n_val, tl, tg, tinh_trang)
            if res:
                st.session_state.search_results = res
                st.rerun()
            else:
                st.session_state.search_results = "EMPTY" # Đánh dấu không tìm thấy
                st.rerun()
                
    # Nút để quay lại xem toàn bộ danh mục (Xóa bộ lọc)
    if st.session_state.search_results is not None:
        if st.button("❌ Xóa bộ lọc và quay lại"):
            st.session_state.search_results = None
            st.rerun()


def sync_all_to_neo4j():
    try:
        with GraphDatabase.driver(neo4j_uri, auth=neo4j_auth) as driver:
            with driver.session() as session:
                # 1. Xóa sạch để đồng bộ mới
                session.run("MATCH (n) DETACH DELETE n")
                
                # 2. Đồng bộ Danh mục (Category & Author)
                res_tl, _ = execute_oracle("SELECT MA_THE_LOAI, TEN_THE_LOAI FROM THE_LOAI")
                for row in res_tl: session.run("MERGE (:Category {id: $id, name: $name})", id=row[0], name=row[1])
                
                res_tg, _ = execute_oracle("SELECT MA_TG, TEN_TG FROM TAC_GIA")
                for row in res_tg: session.run("MERGE (:Author {id: $id, name: $name})", id=row[0], name=row[1])

                # 3. Đồng bộ Người dùng
                res_nd, _ = execute_oracle("SELECT MA_DG, USERNAME, HO_TEN FROM NGUOI_DUNG")
                for row in res_nd: session.run("MERGE (:User {id: $id, username: $un, name: $name})", id=row[0], un=row[1], name=row[2])

                # 4. Đồng bộ Sách & Quan hệ Thể loại
                res_sach, _ = execute_oracle("SELECT MA_SACH, TEN_SACH, MA_THE_LOAI FROM SACH")
                for row in res_sach:
                    session.run("""
                        MATCH (c:Category {id: $cat_id})
                        MERGE (b:Book {id: $bid, title: $title})
                        MERGE (b)-[:BELONGS_TO]->(c)
                    """, bid=row[0], title=row[1], cat_id=row[2])

                # 5. Đồng bộ Quan hệ Tác giả & Phiếu mượn
                res_stg, _ = execute_oracle("SELECT MA_SACH, MA_TG FROM SACH_TAC_GIA")
                for row in res_stg: session.run("MATCH (b:Book {id: $bid}), (a:Author {id: $aid}) MERGE (b)-[:WRITTEN_BY]->(a)", bid=row[0], aid=row[1])
                
                # res_pm, _ = execute_oracle("SELECT MA_DG, MA_SACH, TRANG_THAI FROM PHIEU_MUON")
                # for row in res_pm: session.run("MATCH (u:User {id: $uid}), (b:Book {id: $bid}) MERGE (u)-[:BORROWED {status: $st}]->(b)", uid=row[0], bid=row[1], st=row[2])
                res_pm, _ = execute_oracle("SELECT MA_DG, MA_SACH, TRANG_THAI, SO_LUONG_MUON FROM PHIEU_MUON")
                if res_pm:
                    for row in res_pm:
                        session.run("""
                            MATCH (u:User {id: $uid}), (b:Book {id: $bid})
                            MERGE (u)-[:BORROWED {status: $st, quantity: $qty}]->(b)
                        """, uid=row[0], bid=row[1], st=row[2], qty=row[3])
        return True
    except Exception as e:
        print(f"Lỗi Sync: {e}")
        return False

# 1. Thêm tham số 'prefix' vào hàm
def display_book_grid(data, prefix="catalog"):
    cols = st.columns([1, 2, 1.5, 1.5, 1, 1, 1.2])
    headers = ["Mã Sách", "Tên Sách", "Thể Loại", "Tác Giả", "Năm", "Kho", "Thao tác"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    st.divider()

    # 2. Dùng enumerate để lấy thêm số thứ tự (idx) của từng dòng
    for idx, row in enumerate(data):
        ma_sach, ten_sach, the_loai, tac_gia, nam_xb, so_luong = row
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 2, 1.5, 1.5, 1, 1, 1.2])
        
        c1.text(ma_sach)
        c2.text(ten_sach)
        c3.text(the_loai)
        c4.text(tac_gia)
        c5.text(nam_xb)
        
        if so_luong == 0:
            c6.markdown("<span style='color:red'>0</span>", unsafe_allow_html=True)
        else:
            c6.text(so_luong)

        is_disabled = (so_luong == 0)
        
        # 3. CẬP NHẬT KEY DUY NHẤT: Thêm prefix và idx vào key
        # Ví dụ: borrow_search_S002_0, borrow_catalog_S002_1...
        unique_key = f"borrow_{prefix}_{ma_sach}_{idx}"
        
        if c7.button("📖 Mượn", key=unique_key, disabled=is_disabled, use_container_width=True):
            st.session_state.page = "borrow_detail"
            st.session_state.borrow_book_id = ma_sach
            st.session_state.borrow_book_name = ten_sach
            st.session_state.borrow_book_stock = so_luong
            st.rerun()

if 'search_results' not in st.session_state:
    st.session_state.search_results = None  # Lưu dữ liệu tìm được
if 'page' not in st.session_state:
    st.session_state.page = "catalog" # Mặc định là trang danh mục
if 'borrow_book_id' not in st.session_state:
    st.session_state.borrow_book_id = None
# --- 3. GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống Thư viện Hybrid", layout="wide")

# Khởi tạo session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_name = ""

# --- MÀN HÌNH ĐĂNG NHẬP ---
if not st.session_state.logged_in:
    st.title("📚 Thư viện")
    tab_login, tab_reg = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký User"])

    with tab_login:
        role = st.radio("Bạn là:", ["Độc giả (User)", "Thủ thư (Admin)"], horizontal=True)
        if role == "Độc giả (User)":
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Đăng nhập"):
                # 1. Thêm TRANG_THAI vào câu lệnh SELECT
                sql = "SELECT MA_DG, HO_TEN, TRANG_THAI FROM NGUOI_DUNG WHERE USERNAME = :1 AND PASSWORD = :2"
                res, _ = execute_oracle(sql, [u, p])
                
                if res:
                    # Lấy dữ liệu từ kết quả truy vấn
                    ma_dg, ho_ten, trang_thai = res[0]
                    
                    # 2. Kiểm tra trạng thái tài khoản
                    # Giả định: 1 là hoạt động, 0 là bị khóa
                    if trang_thai == 1:
                        st.session_state.logged_in = True
                        st.session_state.role = "USER"
                        st.session_state.user_id = ma_dg
                        st.session_state.user_name = ho_ten
                        st.success(f"Chào mừng {ho_ten} quay trở lại!")
                        st.rerun()
                    else:
                        # Hiển thị thông báo nếu trạng thái = 0
                        st.error("⚠️ Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Thủ thư để được hỗ trợ!")
                else:
                    st.error("Tài khoản hoặc mật khẩu không đúng!")
        else:
            admin_code = st.text_input("Nhập mã bảo mật Admin", type="password")
            if st.button("Xác thực Admin"):
                if admin_code == ADMIN_SECRET_KEY:
                    st.session_state.logged_in = True
                    st.session_state.role = "ADMIN"
                    st.session_state.user_name = "Quản trị viên"
                    st.rerun()
                else:
                    st.error("Mã Admin không chính xác!")
    
    with tab_reg:
        st.subheader("Tạo tài khoản mới")
        new_u = st.text_input("Username mới")
        new_p = st.text_input("Password mới", type="password")

        new_name = st.text_input("Họ tên")
        new_phone = st.text_input("Số điện thoại")
        
        if st.button("Hoàn tất đăng ký", width="stretch"):
            if new_u and new_p and new_name:
                # 1. Tự động tạo mã độc giả
                new_ma_dg = get_next_id("NGUOI_DUNG", "MA_DG", "DG")
                
                # 2. Lưu vào Oracle
                sql = "INSERT INTO NGUOI_DUNG (MA_DG, USERNAME, PASSWORD, HO_TEN, SO_DIEN_THOAI) VALUES (:1, :2, :3, :4, :5)"
                success, err = execute_oracle(sql, [new_ma_dg, new_u, new_p, new_name, new_phone], is_select=False)
                
                if success:
                    # 3. ĐỒNG BỘ TỰ ĐỘNG SANG NEO4J
                    try:
                        with GraphDatabase.driver(neo4j_uri, auth=neo4j_auth) as driver:
                            with driver.session() as session:
                                session.run("""
                                    MERGE (u:User {id: $id})
                                    SET u.username = $username, 
                                        u.fullName = $name, 
                                        u.phone = $phone
                                """, id=new_ma_dg, username=new_u, name=new_name, phone=new_phone)
                        
                        st.balloons() # Hiệu ứng chúc mừng
                        st.success(f"Đăng ký thành công! Mã của bạn là: {new_ma_dg}")
                        st.info("Tài khoản đã được đồng bộ vào hệ thống gợi ý Graph.")
                    except Exception as neo_err:
                        # Nếu lỗi Neo4j, vẫn báo đăng ký thành công Oracle nhưng cảnh báo phần Sync
                        st.warning(f"Đăng ký thành công nhưng lỗi đồng bộ Graph: {neo_err}")
                else:
                    st.error(f"Lỗi Oracle: {err}")
            else:
                st.warning("Vui lòng điền đầy đủ các thông tin bắt buộc!")
    st.stop()

# --- MÀN HÌNH SAU KHI ĐĂNG NHẬP ---
with st.sidebar:
    st.title("📋 Menu")
    st.write(f"Chào: **{st.session_state.user_name}**")
    
    # NÚT REFRESH AN TOÀN
    if st.button("🔄 Cập nhật dữ liệu (Refresh)"):
        st.rerun()

    if st.button("🚪 Đăng xuất"):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

    if st.session_state.role == "ADMIN":
        st.divider()
        if st.button("⚡ Đồng bộ Neo4j"):
            if sync_all_to_neo4j(): st.toast("Đã đồng bộ!")
        
        # 2. Xóa tất cả dữ liệu (Đặt trong Popover để tiết kiệm diện tích và an toàn)
        with st.popover("🚨 Reset Database"):
            st.warning("Hành động này sẽ xóa sạch toàn bộ dữ liệu trong các Bảng.")
            confirm_code = st.text_input("Nhập mã Admin để xác nhận:", type="password")
            
            if st.button("🔥 XÁC NHẬN XÓA TẤT CẢ", width="stretch"):
                if confirm_code == ADMIN_SECRET_KEY:
                    # Thứ tự xóa để tránh lỗi Constraint (Khóa ngoại)
                    queries = [
                        "DELETE FROM PHIEU_MUON",
                        "DELETE FROM SACH_TAC_GIA",
                        "DELETE FROM SACH",
                        "DELETE FROM THE_LOAI",
                        "DELETE FROM TAC_GIA",
                        "DELETE FROM NGUOI_DUNG"
                    ]
                    
                    success_all = True
                    for sql in queries:
                        status, err = execute_oracle(sql, is_select=False)
                        if status is None:
                            st.error(f"Lỗi Oracle: {err}")
                            success_all = False
                            break
                    
                    # if success_all:
                    #     # Xóa trắng Neo4j
                    #     try:
                    #         with GraphDatabase.driver(neo4j_uri, auth=neo4j_auth) as driver:
                    #             with driver.session() as session:
                    #                 session.run("MATCH (n) DETACH DELETE n")
                    #         st.success("Dữ liệu đã được làm sạch!")
                    #         st.rerun()
                    #     except Exception as e:
                    #         st.error(f"Lỗi Neo4j: {e}")
                    
                    st.success("Dữ liệu đã được làm sạch!")
                    #st.rerun()
                else:
                    st.error("Mã Admin không đúng!")

# --- PHÂN QUYỀN GIAO DIỆN ---
if st.session_state.role == "ADMIN":
    tab_manage, tab_catalog, tab_user, tab_loan = st.tabs(["🛠️ Quản lý kho", "📚 Thư viện sách", "👥 Quản lý người dùng", "📖 Quản lý phiếu mượn"])
    
    with tab_manage:
        # PHẦN THÊM SÁCH
        st.subheader("Thêm sách mới")
        with st.form("add_book_form", clear_on_submit=True):
            b_name = st.text_input("Tên sách")
            b_cat_name = st.text_input("Tên thể loại")
            b_auth_name = st.text_input("Tên tác giả")
            
            # Nhập Năm xuất bản và Số lượng dưới dạng text để dễ xử lý validation
            b_year_input = st.text_input("Năm xuất bản", value="2026")
            b_qty_input = st.text_input("Số lượng thêm vào", value="1")
            
            if st.form_submit_button("Lưu hệ thống"):
                if b_name and b_cat_name and b_auth_name:
                    # --- VALIDATION DỮ LIỆU ---
                    # 1. Kiểm tra Năm xuất bản
                    try:
                        b_year = int(b_year_input)
                        if b_year < 0 or b_year > 2026:
                            b_year = 2026
                    except ValueError:
                        b_year = 2026

                    # 2. Kiểm tra Số lượng
                    try:
                        b_qty = int(b_qty_input)
                        if b_qty <= 0:
                            b_qty = 1
                    except ValueError:
                        b_qty = 1

                    # --- LOGIC XỬ LÝ DATABASE ---
                    # Lấy hoặc tạo Metadata
                    ma_tl = get_or_create_metadata("THE_LOAI", "TL", b_cat_name)
                    ma_tg = get_or_create_metadata("TAC_GIA", "TG", b_auth_name)
                    
                    # Kiểm tra sách tồn tại (Chỉ so sánh thông tin định danh, không so sánh số lượng)
                    check_sql = """
                        SELECT s.MA_SACH 
                        FROM SACH s
                        JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
                        WHERE UPPER(s.TEN_SACH) = UPPER(:1) 
                        AND s.MA_THE_LOAI = :2 
                        AND s.NAM_XB = :3 
                        AND stg.MA_TG = :4
                    """
                    existing_book, _ = execute_oracle(check_sql, [b_name, ma_tl, b_year, ma_tg])
                    
                    if existing_book:
                        # TRƯỜNG HỢP 1: Đã có sách -> Cộng dồn số lượng
                        ma_sach_ton_tai = existing_book[0][0]
                        update_sql = "UPDATE SACH SET so_luong = so_luong + :1 WHERE MA_SACH = :2"
                        success, _ = execute_oracle(update_sql, [b_qty, ma_sach_ton_tai], is_select=False)
                        
                        if success:
                            st.success(f"Đã cập nhật! Mã {ma_sach_ton_tai} tăng thêm {b_qty} cuốn.")
                    else:
                        # TRƯỜNG HỢP 2: Sách mới hoàn toàn -> Chèn mới với số lượng đã nhập
                        new_id = get_next_id("SACH", "MA_SACH", "S")
                        sql_book = "INSERT INTO SACH (MA_SACH, TEN_SACH, NAM_XB, MA_THE_LOAI, SO_LUONG) VALUES (:1, :2, :3, :4, :5)"
                        success_b, _ = execute_oracle(sql_book, [new_id, b_name, b_year, ma_tl, b_qty], is_select=False)
                        
                        # Chèn bảng trung gian tác giả
                        execute_oracle("INSERT INTO SACH_TAC_GIA (MA_SACH, MA_TG) VALUES (:1, :2)", [new_id, ma_tg], is_select=False)
                        
                        if success_b:
                            st.success(f"Thêm mới thành công! Mã sách: {new_id} với số lượng: {b_qty}")
                else:
                    st.warning("Vui lòng nhập đầy đủ tên sách, thể loại và tác giả!")
                        

        st.divider()
        st.subheader("📋 Chỉnh sửa / Xóa sách toàn diện")

        # 1. Lấy danh sách sách đầy đủ thông tin (Thêm cột SO_LUONG)
        sql_fetch_all = """
            SELECT 
                s.MA_SACH, 
                s.TEN_SACH, 
                t.TEN_THE_LOAI, 
                LISTAGG(tg.TEN_TG, ', ') WITHIN GROUP (ORDER BY tg.TEN_TG) AS TAC_GIA,
                s.NAM_XB,
                s.SO_LUONG
            FROM SACH s
            JOIN THE_LOAI t ON s.MA_THE_LOAI = t.MA_THE_LOAI
            LEFT JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
            LEFT JOIN TAC_GIA tg ON stg.MA_TG = tg.MA_TG
            GROUP BY s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, s.NAM_XB, s.SO_LUONG
            ORDER BY s.MA_SACH
        """
        res_manage, _ = execute_oracle(sql_fetch_all)

        if res_manage:
            book_dict = {
                row[0]: {
                    'name': row[1],
                    'cat': row[2],
                    'auth': row[3],
                    'year': row[4],
                    'qty': row[5]
                } for row in res_manage
            }
            
            selected_id = st.selectbox("Chọn mã sách cần xử lý:", options=list(book_dict.keys()))
            current_book = book_dict[selected_id]

            with st.form("comprehensive_edit_form"):
                st.info(f"Đang xử lý mã sách: **{selected_id}**")
                
                edit_name = st.text_input("Tên sách:", value=current_book['name'])
                edit_cat = st.text_input("Thể loại:", value=current_book['cat'])
                edit_auth = st.text_input("Tác giả:", value=current_book['auth'])
                
                # Dùng text_input cho Năm và Số lượng để xử lý lỗi nhập liệu linh hoạt
                edit_year_raw = st.text_input("Năm xuất bản:", value=str(current_book['year']))
                edit_qty_raw = st.text_input("Số lượng trong kho:", value=str(current_book['qty']))
                
                col_edit, col_del = st.columns(2)
                with col_edit:
                    submit_update = st.form_submit_button("💾 Cập nhật thay đổi")
                with col_del:
                    submit_delete = st.form_submit_button("🗑️ Xóa sách khỏi hệ thống")

                # --- XỬ LÝ CẬP NHẬT ---
                if submit_update:
                    # VALIDATION: Kiểm tra Năm xuất bản
                    try:
                        final_year = int(edit_year_raw)
                        if final_year < 0 or final_year > 2026: # Giả sử năm hiện tại là 2026
                            final_year = current_book['year'] # Không hợp lệ thì giữ nguyên
                    except ValueError:
                        final_year = current_book['year']

                    # VALIDATION: Kiểm tra Số lượng
                    try:
                        final_qty = int(edit_qty_raw)
                        if final_qty < 0: # Chấp nhận bằng 0, nhưng không chấp nhận âm
                            final_qty = current_book['qty'] # Không hợp lệ thì giữ nguyên
                    except ValueError:
                        final_qty = current_book['qty']

                    # 1. Xử lý Metadata
                    new_ma_tl = get_or_create_metadata("THE_LOAI", "TL", edit_cat)
                    new_ma_tg = get_or_create_metadata("TAC_GIA", "TG", edit_auth)
                    
                    # 2. Cập nhật bảng SACH (Thêm SO_LUONG)
                    sql_up_sach = "UPDATE SACH SET TEN_SACH = :1, NAM_XB = :2, MA_THE_LOAI = :3, SO_LUONG = :4 WHERE MA_SACH = :5"
                    execute_oracle(sql_up_sach, [edit_name, final_year, new_ma_tl, final_qty, selected_id], is_select=False)
                    
                    # 3. Cập nhật bảng trung gian Tác giả
                    execute_oracle("DELETE FROM SACH_TAC_GIA WHERE MA_SACH = :1", [selected_id], is_select=False)
                    execute_oracle("INSERT INTO SACH_TAC_GIA (MA_SACH, MA_TG) VALUES (:1, :2)", [selected_id, new_ma_tg], is_select=False)
                    
                    st.success(f"Đã cập nhật sách {selected_id}. (Năm: {final_year}, SL: {final_qty})")
                    st.rerun()

                # --- XỬ LÝ XÓA ---
                if submit_delete:
                    # Lưu ý: Xóa sách ở đây là xóa hẳn bản ghi đầu mục, không phụ thuộc vào số lượng
                    execute_oracle("DELETE FROM SACH_TAC_GIA WHERE MA_SACH = :1", [selected_id], is_select=False)
                    execute_oracle("DELETE FROM SACH WHERE MA_SACH = :1", [selected_id], is_select=False)
                    st.warning(f"Đã xóa hoàn toàn sách {selected_id} khỏi cơ sở dữ liệu!")
                    st.rerun()
        else:
            st.info("Chưa có dữ liệu sách để chỉnh sửa.")
    with tab_catalog:
        display_comprehensive_catalog()
        st.divider()
        search_logic()
    with tab_user:
        st.header("👥 Quản lý người dùng")
        search_term = st.text_input("Tìm kiếm người dùng (Tên, SĐT, Mã):")
        display_user_management(search_term)
    with tab_loan:
        display_borrow_management()

else: # USER ROLE
    tab_main, tab_graph, tab_history_loan = st.tabs(["📚 Thư viện sách", "💡 Gợi ý cho bạn", "📖 Lịch sử mượn"])
    with tab_main:
        
        # Màn hình chính của Độc giả
        if st.session_state.page == "catalog":
            # Gọi hàm hiển thị thanh tìm kiếm
            # display_comprehensive_catalog_user()
            # st.divider()
            # search_logic_user()
            search_logic_user() # Luôn hiện bộ lọc ở trên cùng

            st.divider() # Vạch kẻ phân cách

            # Logic điều hướng bảng:
            if st.session_state.search_results is None:
                # TRƯỜNG HỢP 1: Chưa tìm kiếm -> Hiện danh mục mặc định
                st.subheader("📋 Danh mục sách chi tiết")
                sql_all = """
                    SELECT s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, 
                        LISTAGG(tg.TEN_TG, ', ') WITHIN GROUP (ORDER BY tg.TEN_TG),
                        s.NAM_XB, s.SO_LUONG
                    FROM SACH s
                    JOIN THE_LOAI t ON s.MA_THE_LOAI = t.MA_THE_LOAI
                    LEFT JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
                    LEFT JOIN TAC_GIA tg ON stg.MA_TG = tg.MA_TG
                    GROUP BY s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, s.NAM_XB, s.SO_LUONG
                    ORDER BY s.MA_SACH
                """
                data_all, _ = execute_oracle(sql_all)
                if data_all:
                    display_book_grid(data_all, prefix="main_catalog")

            elif st.session_state.search_results == "EMPTY":
                # TRƯỜNG HỢP 2: Đã tìm nhưng không có kết quả
                st.info("⚠️ Không tìm thấy kết quả phù hợp với bộ lọc của bạn.")

            else:
                # TRƯỜNG HỢP 3: Có kết quả tìm kiếm -> Chỉ hiện bảng này
                st.subheader("🎯 Kết quả tìm kiếm phù hợp")
                display_book_grid(st.session_state.search_results, prefix="search_res")
                        # Gọi hàm hiển thị danh mục mặc định nếu không tìm kiếm
                        # data, _ = execute_oracle("SELECT ...")
                        # display_book_grid(data)
        elif st.session_state.page == "borrow_detail":
            borrow_book_page()
    with tab_graph:
        display_recommendations()
    with tab_history_loan:
        display_user_borrow_history()