import os
import streamlit as st
import oracledb
from neo4j import GraphDatabase
from dotenv import load_dotenv
#import pandas as pd
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
PAGE_SIZE_DEFAULT = 10
PAGE_SIZE_SEARCH_ALL = 50
PAGE_SIZE_USER = 20
PAGE_SIZE_LOAN = 20
PAGE_SIZE_HISTORY = 10

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
        cursor.arraysize = 500
        cursor.prefetchrows = 500
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


def query_books_page(page=1, page_size=PAGE_SIZE_DEFAULT, ma_sach=None, ten_sach=None,
                     nam_xb=None, the_loai=None, tac_gia=None, tinh_trang="Tất cả"):
    base_sql = """
        SELECT s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI,
               LISTAGG(tg.TEN_TG, ', ') WITHIN GROUP (ORDER BY tg.TEN_TG) AS TAC_GIA,
               s.NAM_XB, s.SO_LUONG
        FROM SACH s
        JOIN THE_LOAI t ON s.MA_THE_LOAI = t.MA_THE_LOAI
        LEFT JOIN SACH_TAC_GIA stg ON s.MA_SACH = stg.MA_SACH
        LEFT JOIN TAC_GIA tg ON stg.MA_TG = tg.MA_TG
        WHERE 1=1
    """
    params = {}

    if ma_sach:
        base_sql += " AND s.MA_SACH = :ma_sach"
        params["ma_sach"] = ma_sach
    if ten_sach:
        base_sql += " AND UPPER(s.TEN_SACH) LIKE UPPER(:ten_sach)"
        params["ten_sach"] = f"%{ten_sach}%"
    if nam_xb:
        base_sql += " AND s.NAM_XB = :nam_xb"
        params["nam_xb"] = nam_xb
    if the_loai:
        base_sql += " AND UPPER(t.TEN_THE_LOAI) LIKE UPPER(:the_loai)"
        params["the_loai"] = f"%{the_loai}%"
    if tac_gia:
        base_sql += " AND UPPER(tg.TEN_TG) LIKE UPPER(:tac_gia)"
        params["tac_gia"] = f"%{tac_gia}%"

    if tinh_trang == "Còn hàng":
        base_sql += " AND s.SO_LUONG > 0"
    elif tinh_trang == "Hết hàng":
        base_sql += " AND s.SO_LUONG = 0"

    base_sql += " GROUP BY s.MA_SACH, s.TEN_SACH, t.TEN_THE_LOAI, s.NAM_XB, s.SO_LUONG"
    base_sql += " ORDER BY s.MA_SACH"

    offset = (page - 1) * page_size
    paginated_sql = base_sql + f" OFFSET {offset} ROWS FETCH NEXT {page_size + 1} ROWS ONLY"

    rows, _ = execute_oracle(paginated_sql, params)
    if rows is None:
        return [], False

    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def query_users_page(page=1, page_size=PAGE_SIZE_USER, search_term=None, status_option="Tất cả"):
    base_sql = "SELECT MA_DG, USERNAME, HO_TEN, SO_DIEN_THOAI, TRANG_THAI FROM NGUOI_DUNG WHERE 1=1"
    params = []

    if status_option == "Hoạt động":
        base_sql += " AND TRANG_THAI = 1"
    elif status_option == "Đã khóa":
        base_sql += " AND TRANG_THAI = 0"

    if search_term:
        base_sql += " AND (UPPER(HO_TEN) LIKE UPPER(:1) OR SO_DIEN_THOAI LIKE :2 OR MA_DG = :3 OR UPPER(USERNAME) LIKE UPPER(:4))"
        search_val = f"%{search_term}%"
        params = [search_val, search_val, search_term, search_val]

    base_sql += " ORDER BY MA_DG"
    offset = (page - 1) * page_size
    paginated_sql = base_sql + f" OFFSET {offset} ROWS FETCH NEXT {page_size + 1} ROWS ONLY"

    rows, _ = execute_oracle(paginated_sql, params)
    if rows is None:
        return [], False

    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def query_loans_page(page=1, page_size=PAGE_SIZE_LOAN, search_kw=None, status_filter="Tất cả", overdue_filter=False, date_m=None, date_h=None):
    base_sql = """
        SELECT pm.MA_PM, nd.MA_DG, nd.HO_TEN, s.TEN_SACH, pm.SO_LUONG_MUON,
               pm.NGAY_MUON, pm.NGAY_TRA_DU_KIEN, pm.TRANG_THAI, s.MA_SACH
        FROM PHIEU_MUON pm
        JOIN NGUOI_DUNG nd ON pm.MA_DG = nd.MA_DG
        JOIN SACH s ON pm.MA_SACH = s.MA_SACH
        WHERE pm.TRANG_THAI != 'Chờ duyệt'
    """
    params = []

    if search_kw:
        base_sql += " AND (UPPER(nd.HO_TEN) LIKE UPPER(:1) OR UPPER(s.TEN_SACH) LIKE UPPER(:2) OR nd.MA_DG = :3)"
        params += [f"%{search_kw}%", f"%{search_kw}%", search_kw]

    if status_filter != "Tất cả":
        base_sql += f" AND pm.TRANG_THAI = :{len(params)+1}"
        params.append(status_filter)

    if overdue_filter:
        base_sql += " AND pm.NGAY_TRA_DU_KIEN < SYSDATE AND pm.TRANG_THAI = 'Đang mượn'"

    if date_m:
        base_sql += f" AND TRUNC(pm.NGAY_MUON) = :{len(params)+1}"
        params.append(date_m)

    if date_h:
        base_sql += f" AND TRUNC(pm.NGAY_TRA_DU_KIEN) = :{len(params)+1}"
        params.append(date_h)

    base_sql += " ORDER BY pm.NGAY_TRA_DU_KIEN ASC"
    offset = (page - 1) * page_size
    paginated_sql = base_sql + f" OFFSET {offset} ROWS FETCH NEXT {page_size + 1} ROWS ONLY"

    rows, _ = execute_oracle(paginated_sql, params)
    if rows is None:
        return [], False

    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def query_user_history_page(page=1, page_size=PAGE_SIZE_HISTORY, ma_dg=None, search_book=None, status_filter="Tất cả", date_m=None, date_h=None):
    base_sql = """
        SELECT pm.MA_PM, s.TEN_SACH, pm.SO_LUONG_MUON,
               pm.NGAY_MUON, pm.NGAY_TRA_DU_KIEN, pm.TRANG_THAI
        FROM PHIEU_MUON pm
        JOIN SACH s ON pm.MA_SACH = s.MA_SACH
        WHERE pm.MA_DG = :1
    """
    params = [ma_dg]

    if search_book:
        base_sql += f" AND UPPER(s.TEN_SACH) LIKE UPPER(:{len(params)+1})"
        params.append(f"%{search_book}%")

    if status_filter != "Tất cả":
        base_sql += f" AND pm.TRANG_THAI = :{len(params)+1}"
        params.append(status_filter)

    if date_m:
        base_sql += f" AND TRUNC(pm.NGAY_MUON) = :{len(params)+1}"
        params.append(date_m)

    if date_h:
        base_sql += f" AND TRUNC(pm.NGAY_TRA_DU_KIEN) = :{len(params)+1}"
        params.append(date_h)

    base_sql += " ORDER BY pm.NGAY_MUON DESC"
    offset = (page - 1) * page_size
    paginated_sql = base_sql + f" OFFSET {offset} ROWS FETCH NEXT {page_size + 1} ROWS ONLY"

    rows, _ = execute_oracle(paginated_sql, params)
    if rows is None:
        return [], False

    has_more = len(rows) > page_size
    return rows[:page_size], has_more


def render_book_page(rows, page, has_more, prefix="catalog", state_key=None):
    if not rows:
        st.info("Không có kết quả phù hợp.")
        return

    display_book_grid(rows, prefix=prefix)
    col_prev, col_next = st.columns([1, 1])
    if state_key is None:
        state_key = f"{prefix}_page"

    if col_prev.button("← Trang trước", key=f"prev_{prefix}", disabled=page <= 1):
        st.session_state[state_key] = page - 1
        st.rerun()
    if col_next.button("Trang sau →", key=f"next_{prefix}", disabled=not has_more):
        st.session_state[state_key] = page + 1
        st.rerun()


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

    if 'admin_user_page' not in st.session_state:
        st.session_state.admin_user_page = 1

    rows, has_more = query_users_page(
        page=st.session_state.admin_user_page,
        page_size=PAGE_SIZE_USER,
        search_term=search_term,
        status_option=status_option
    )

    if rows:
        st.write(f"Hiển thị trang **{st.session_state.admin_user_page}** với **{len(rows)}** tài khoản")
        cols = st.columns([1, 1.5, 2, 1.5, 1.2, 1.2])
        headers = ["Mã ĐG", "Username", "Họ Tên", "SĐT", "Trạng Thái", "Thao tác"]
        for col, header in zip(cols, headers):
            col.markdown(f"**{header}**")
        
        st.divider()

        for row in rows:
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
                sync_user_node(ma_dg)
                
                st.toast(f"Đã cập nhật trạng thái cho {username}!")
                st.rerun()

        col_prev, col_next = st.columns([1, 1])
        if col_prev.button("← Trang trước", key="user_prev", disabled=st.session_state.admin_user_page <= 1):
            st.session_state.admin_user_page -= 1
            st.rerun()
        if col_next.button("Trang sau →", key="user_next", disabled=not has_more):
            st.session_state.admin_user_page += 1
            st.rerun()
    else:
        st.info("Không tìm thấy tài khoản phù hợp.")

def display_user_borrow_history():
    st.subheader("📖 Lịch sử mượn sách của bạn")
    
    ma_dg = st.session_state.get("user_id") 
    
    if not ma_dg:
        st.warning("Vui lòng đăng nhập để xem lịch sử.")
        return

    if 'user_history_page' not in st.session_state:
        st.session_state.user_history_page = 1

    with st.expander("🔍 Tìm kiếm trong lịch sử của bạn", expanded=True):
        f1, f2 = st.columns([2, 1])
        search_book = f1.text_input("Nhập tên sách cần tìm")
        status_filter = f2.selectbox("Trạng Thái", ["Tất cả", "Đang mượn", "Đã trả"], index=0)

        f3, f4 = st.columns(2)
        date_m = f3.date_input("Lọc theo ngày mượn", value=None)
        date_h = f4.date_input("Lọc theo hạn trả dự kiến", value=None)

    rows, has_more = query_user_history_page(
        page=st.session_state.user_history_page,
        page_size=PAGE_SIZE_HISTORY,
        ma_dg=ma_dg,
        search_book=search_book,
        status_filter=status_filter,
        date_m=date_m,
        date_h=date_h
    )

    if rows:
        st.write(f"Hiển thị trang **{st.session_state.user_history_page}** với **{len(rows)}** bản ghi")
        cols = st.columns([1, 2, 0.8, 1.2, 1.2, 1])
        headers = ["Mã PM", "Tên Sách", "SL", "Ngày Mượn", "Hạn Trả", "Trạng Thái"]
        for col, h in zip(cols, headers): col.markdown(f"**{h}**")
        st.divider()

        for row in rows:
            ma_pm, ten_sach, sl_muon, ngay_m, ngay_h, status = row
            c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 0.8, 1.2, 1.2, 1])
            
            c1.text(ma_pm)
            c2.text(ten_sach)
            c3.text(sl_muon)
            c4.text(ngay_m.strftime('%d/%m/%Y'))
            
            is_overdue = ngay_h < datetime.now() and status == 'Đang mượn'
            h_color = "red" if is_overdue else "black"
            c5.markdown(f"<span style='color:{h_color}'>{ngay_h.strftime('%d/%m/%Y')}</span>", unsafe_allow_html=True)
            
            st_icon = "🔵" if status == "Đang mượn" else "🟢"
            c6.text(f"{st_icon} {status}")

        col_prev, col_next = st.columns([1, 1])
        if col_prev.button("← Trang trước", key="history_prev", disabled=st.session_state.user_history_page <= 1):
            st.session_state.user_history_page -= 1
            st.rerun()
        if col_next.button("Trang sau →", key="history_next", disabled=not has_more):
            st.session_state.user_history_page += 1
            st.rerun()
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
                            sync_book_node(ma_sach)
                            sync_borrow_record(ma_pm_moi)
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

    rows, has_more = query_loans_page(
        page=st.session_state.admin_loan_page if 'admin_loan_page' in st.session_state else 1,
        page_size=PAGE_SIZE_LOAN,
        search_kw=search_kw,
        status_filter=status_filter,
        overdue_filter=overdue_filter,
        date_m=date_m,
        date_h=date_h
    )

    if rows:
        st.write(f"Hiển thị trang **{st.session_state.admin_loan_page}** với **{len(rows)}** phiếu mượn")
        cols = st.columns([0.7, 1.2, 1.2, 0.5, 1, 1, 0.8, 1])
        headers = ["Mã PM", "Độc Giả", "Tên Sách", "SL", "Ngày Mượn", "Hạn Trả", "Trạng Thái", "Thao tác"]
        for col, h in zip(cols, headers): col.markdown(f"**{h}**")
        st.divider()

        for row in rows:
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

        col_prev, col_next = st.columns([1, 1])
        if col_prev.button("← Trang trước", key="loan_prev", disabled=st.session_state.admin_loan_page <= 1):
            st.session_state.admin_loan_page -= 1
            st.rerun()
        if col_next.button("Trang sau →", key="loan_next", disabled=not has_more):
            st.session_state.admin_loan_page += 1
            st.rerun()
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
    
    sync_borrow_record(ma_pm)
    sync_user_node(ma_dg)
    sync_book_node(ma_sach)
    
    st.success(f"Đã xử lý trả sách cho phiếu {ma_pm}. Tài khoản {ma_dg} đã được mở khóa.")
    st.rerun()

def display_comprehensive_catalog():
    st.subheader("📋 Danh mục sách chi tiết (Oracle)")

    if 'admin_catalog_page' not in st.session_state:
        st.session_state.admin_catalog_page = 1

    rows, has_more = query_books_page(page=st.session_state.admin_catalog_page, page_size=PAGE_SIZE_DEFAULT)
    
    if rows:
        display_book_grid(rows, prefix="admin_catalog", show_borrow_button=False)
        col_prev, col_next = st.columns([1, 1])
        if col_prev.button("← Trang trước", key="admin_cat_prev", disabled=st.session_state.admin_catalog_page <= 1):
            st.session_state.admin_catalog_page -= 1
            st.rerun()
        if col_next.button("Trang sau →", key="admin_cat_next", disabled=not has_more):
            st.session_state.admin_catalog_page += 1
            st.rerun()
    else:
        st.info("Chưa có dữ liệu sách.")

def is_search_all(filters: dict) -> bool:
    return (
        not filters.get("ma_sach")
        and not filters.get("ten_sach")
        and not filters.get("nam_xb")
        and not filters.get("the_loai")
        and not filters.get("tac_gia")
        and filters.get("tinh_trang") == "Tất cả"
    )


def search_books_advanced(ma_sach=None, ten_sach=None, nam_xb=None, the_loai=None, tac_gia=None, tinh_trang="Tất cả", page=1, page_size=PAGE_SIZE_DEFAULT):
    return query_books_page(page=page, page_size=page_size,
                            ma_sach=ma_sach, ten_sach=ten_sach,
                            nam_xb=nam_xb, the_loai=the_loai,
                            tac_gia=tac_gia, tinh_trang=tinh_trang)

def search_logic():
    st.subheader("🔍 Bộ lọc tìm kiếm")

    c1, c2, c3 = st.columns(3)
    with c1:
        ma = st.text_input("Mã sách", key="admin_search_ma")
    with c2:
        ten = st.text_input("Tên sách", key="admin_search_ten")
    with c3:
        nam_raw = st.text_input("Năm xuất bản", key="admin_search_nam")

    c4, c5, c6 = st.columns(3)
    with c4:
        tl = st.text_input("Thể loại", key="admin_search_tl")
    with c5:
        tg = st.text_input("Tác giả", key="admin_search_tg")
    with c6:
        tinh_trang = st.selectbox("Tình trạng kho", ["Tất cả", "Còn hàng", "Hết hàng"], key="admin_search_tinh_trang")

    if st.button("Bắt đầu tìm", width="stretch", key="admin_search_button"):
        valid = True
        n_val = None
        if nam_raw:
            try:
                n_val = int(nam_raw)
                if n_val < 0 or n_val > 2026:
                    st.error(f"❌ Năm '{nam_raw}' không hợp lệ (0-2026)")
                    valid = False
            except ValueError:
                st.error("❌ Năm phải là số nguyên!")
                valid = False

        if valid:
            st.session_state.admin_search_filters = {
                "ma_sach": ma or None,
                "ten_sach": ten or None,
                "nam_xb": n_val,
                "the_loai": tl or None,
                "tac_gia": tg or None,
                "tinh_trang": tinh_trang,
            }
            st.session_state.admin_search_page = 1
            st.rerun()

    if st.session_state.get("admin_search_filters"):
        filters = st.session_state.admin_search_filters
        st.subheader("🎯 Kết quả tìm kiếm phù hợp")
        page = st.session_state.get("admin_search_page", 1)
        page_size = PAGE_SIZE_SEARCH_ALL if is_search_all(filters) else PAGE_SIZE_DEFAULT
        rows, has_more = search_books_advanced(
            ma_sach=filters["ma_sach"],
            ten_sach=filters["ten_sach"],
            nam_xb=filters["nam_xb"],
            the_loai=filters["the_loai"],
            tac_gia=filters["tac_gia"],
            tinh_trang=filters["tinh_trang"],
            page=page,
            page_size=page_size
        )
        render_book_page(rows, page, has_more, prefix="admin_search", state_key="admin_search_page")

        if st.button("❌ Xóa bộ lọc và quay lại", key="admin_search_clear"):
            st.session_state.admin_search_filters = None
            st.session_state.admin_search_page = 1
            st.rerun()

def search_logic_user():
    st.subheader("🔍 Bộ lọc tìm kiếm")

    c1, c2, c3 = st.columns(3)
    with c1:
        ma = st.text_input("Mã sách", key="search_ma")
    with c2:
        ten = st.text_input("Tên sách", key="search_ten")
    with c3:
        nam_raw = st.text_input("Năm xuất bản", key="search_nam")

    c4, c5, c6 = st.columns(3)
    with c4:
        tl = st.text_input("Thể loại", key="search_tl")
    with c5:
        tg = st.text_input("Tác giả", key="search_tg")
    with c6:
        tinh_trang = st.selectbox("Tình trạng kho", ["Tất cả", "Còn hàng", "Hết hàng"], key="search_tinh_trang")

    if st.button("Bắt đầu tìm", width="stretch"):
        valid = True
        n_val = None
        if nam_raw:
            try:
                n_val = int(nam_raw)
                if n_val < 0 or n_val > 2026:
                    st.error(f"❌ Năm '{nam_raw}' không hợp lệ (0-2026)")
                    valid = False
            except ValueError:
                st.error("❌ Năm phải là số nguyên!")
                valid = False

        if valid:
            st.session_state.user_search_filters = {
                "ma_sach": ma or None,
                "ten_sach": ten or None,
                "nam_xb": n_val,
                "the_loai": tl or None,
                "tac_gia": tg or None,
                "tinh_trang": tinh_trang,
            }
            st.session_state.user_search_page = 1
            st.rerun()

    if st.session_state.get("user_search_filters"):
        if st.button("❌ Xóa bộ lọc và quay lại"):
            st.session_state.user_search_filters = None
            st.session_state.user_search_page = 1
            st.rerun()


def _chunked(iterable, batch_size):
    for i in range(0, len(iterable), batch_size):
        yield iterable[i:i + batch_size]


def _neo4j_batch_run(session, query, rows, batch_size=500):
    if not rows:
        return
    for batch in _chunked(rows, batch_size):
        session.run(query, rows=batch)


def sync_all_to_neo4j():
    try:
        with GraphDatabase.driver(neo4j_uri, auth=neo4j_auth) as driver:
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")

                res_tl, _ = execute_oracle("SELECT MA_THE_LOAI, TEN_THE_LOAI FROM THE_LOAI")
                categories = [{"id": row[0], "name": row[1]} for row in res_tl] if res_tl else []
                _neo4j_batch_run(session, "UNWIND $rows AS row MERGE (c:Category {id: row.id}) SET c.name = row.name", categories)

                res_tg, _ = execute_oracle("SELECT MA_TG, TEN_TG FROM TAC_GIA")
                authors = [{"id": row[0], "name": row[1]} for row in res_tg] if res_tg else []
                _neo4j_batch_run(session, "UNWIND $rows AS row MERGE (a:Author {id: row.id}) SET a.name = row.name", authors)

                res_nd, _ = execute_oracle("SELECT MA_DG, USERNAME, HO_TEN FROM NGUOI_DUNG")
                users = [{"id": row[0], "username": row[1], "name": row[2]} for row in res_nd] if res_nd else []
                _neo4j_batch_run(session, "UNWIND $rows AS row MERGE (u:User {id: row.id}) SET u.username = row.username, u.name = row.name", users)

                res_sach, _ = execute_oracle("SELECT MA_SACH, TEN_SACH, MA_THE_LOAI FROM SACH")
                books = [{"bid": row[0], "title": row[1], "cat_id": row[2]} for row in res_sach] if res_sach else []
                _neo4j_batch_run(
                    session,
                    "UNWIND $rows AS row MERGE (b:Book {id: row.bid}) SET b.title = row.title MERGE (c:Category {id: row.cat_id}) MERGE (b)-[:BELONGS_TO]->(c)",
                    books
                )

                res_stg, _ = execute_oracle("SELECT MA_SACH, MA_TG FROM SACH_TAC_GIA")
                book_authors = [{"bid": row[0], "aid": row[1]} for row in res_stg] if res_stg else []
                _neo4j_batch_run(
                    session,
                    "UNWIND $rows AS row MATCH (b:Book {id: row.bid}), (a:Author {id: row.aid}) MERGE (b)-[:WRITTEN_BY]->(a)",
                    book_authors
                )

                res_pm, _ = execute_oracle("SELECT MA_DG, MA_SACH, TRANG_THAI, SO_LUONG_MUON FROM PHIEU_MUON")
                borrow_rows = [{"uid": row[0], "bid": row[1], "st": row[2], "qty": row[3]} for row in res_pm] if res_pm else []
                _neo4j_batch_run(
                    session,
                    "UNWIND $rows AS row MATCH (u:User {id: row.uid}), (b:Book {id: row.bid}) MERGE (u)-[r:BORROWED]->(b) SET r.status = row.st, r.quantity = row.qty",
                    borrow_rows
                )
        return True
    except Exception as e:
        print(f"Lỗi Sync: {e}")
        return False


def get_neo4j_session():
    driver = get_neo4j_driver()
    if not driver:
        return None
    try:
        return driver.session()
    except Exception as e:
        print(f"Neo4j session error: {e}")
        return None


def sync_category_node(session, ma_the_loai):
    res, _ = execute_oracle("SELECT TEN_THE_LOAI FROM THE_LOAI WHERE MA_THE_LOAI = :1", [ma_the_loai])
    if res:
        session.run("MERGE (:Category {id: $id, name: $name})", id=ma_the_loai, name=res[0][0])


def sync_author_node(session, ma_tg):
    res, _ = execute_oracle("SELECT TEN_TG FROM TAC_GIA WHERE MA_TG = :1", [ma_tg])
    if res:
        session.run("MERGE (:Author {id: $id, name: $name})", id=ma_tg, name=res[0][0])


def sync_user_node(ma_dg):
    session = get_neo4j_session()
    if not session:
        return False
    res, _ = execute_oracle("SELECT USERNAME, HO_TEN, SO_DIEN_THOAI, TRANG_THAI FROM NGUOI_DUNG WHERE MA_DG = :1", [ma_dg])
    if not res:
        return False
    username, ho_ten, phone, trang_thai = res[0]
    active = 1 if trang_thai == 1 else 0
    try:
        with session as s:
            s.run(
                "MERGE (u:User {id: $id}) SET u.username = $username, u.name = $name, u.phone = $phone, u.active = $active",
                id=ma_dg, username=username, name=ho_ten, phone=phone, active=active
            )
        return True
    except Exception as e:
        print(f"Lỗi sync user Neo4j: {e}")
        return False


def sync_book_node(ma_sach):
    session = get_neo4j_session()
    if not session:
        return False
    res, _ = execute_oracle(
        "SELECT TEN_SACH, MA_THE_LOAI, NAM_XB, SO_LUONG FROM SACH WHERE MA_SACH = :1", [ma_sach]
    )
    if not res:
        remove_book_from_neo4j(ma_sach)
        return False
    title, ma_the_loai, nam_xb, so_luong = res[0]
    try:
        with session as s:
            sync_category_node(s, ma_the_loai)
            s.run(
                "MERGE (b:Book {id: $id}) SET b.title = $title, b.year = $year, b.stock = $stock",
                id=ma_sach, title=title, year=nam_xb, stock=so_luong
            )
            s.run("MATCH (b:Book {id: $id})-[r:WRITTEN_BY]->() DELETE r", id=ma_sach)
            res_auth, _ = execute_oracle("SELECT MA_TG FROM SACH_TAC_GIA WHERE MA_SACH = :1", [ma_sach])
            if res_auth:
                for auth_row in res_auth:
                    ma_tg = auth_row[0]
                    sync_author_node(s, ma_tg)
                    s.run(
                        "MATCH (b:Book {id: $bid}), (a:Author {id: $aid}) MERGE (b)-[:WRITTEN_BY]->(a)",
                        bid=ma_sach, aid=ma_tg
                    )
            s.run(
                "MATCH (b:Book {id: $bid}), (c:Category {id: $cid}) MERGE (b)-[:BELONGS_TO]->(c)",
                bid=ma_sach, cid=ma_the_loai
            )
        return True
    except Exception as e:
        print(f"Lỗi sync book Neo4j: {e}")
        return False


def remove_book_from_neo4j(ma_sach):
    session = get_neo4j_session()
    if not session:
        return False
    try:
        with session as s:
            s.run("MATCH (b:Book {id: $id}) DETACH DELETE b", id=ma_sach)
        return True
    except Exception as e:
        print(f"Lỗi xóa sách trên Neo4j: {e}")
        return False


def sync_borrow_record(ma_pm):
    session = get_neo4j_session()
    if not session:
        return False
    res, _ = execute_oracle(
        "SELECT MA_DG, MA_SACH, TRANG_THAI, SO_LUONG_MUON FROM PHIEU_MUON WHERE MA_PM = :1", [ma_pm]
    )
    if not res:
        return False
    ma_dg, ma_sach, trang_thai, so_luong_muon = res[0]
    try:
        with session as s:
            s.run(
                "MATCH (u:User {id: $uid}), (b:Book {id: $bid}) MERGE (u)-[r:BORROWED]->(b) SET r.status = $status, r.quantity = $qty",
                uid=ma_dg, bid=ma_sach, status=trang_thai, qty=so_luong_muon
            )
        return True
    except Exception as e:
        print(f"Lỗi sync borrow Neo4j: {e}")
        return False

# 1. Thêm tham số 'prefix' và 'show_borrow_button' vào hàm
def display_book_grid(data, prefix="catalog", show_borrow_button=True):
    if show_borrow_button:
        cols = st.columns([1, 2, 1.5, 1.5, 1, 1, 1.2])
        headers = ["Mã Sách", "Tên Sách", "Thể Loại", "Tác Giả", "Năm", "Kho", "Thao tác"]
    else:
        cols = st.columns([1, 2, 1.5, 1.5, 1, 1])
        headers = ["Mã Sách", "Tên Sách", "Thể Loại", "Tác Giả", "Năm", "Kho"]
    
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    st.divider()

    # 2. Dùng enumerate để lấy thêm số thứ tự (idx) của từng dòng
    for idx, row in enumerate(data):
        ma_sach, ten_sach, the_loai, tac_gia, nam_xb, so_luong = row
        
        if show_borrow_button:
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 2, 1.5, 1.5, 1, 1, 1.2])
        else:
            c1, c2, c3, c4, c5, c6 = st.columns([1, 2, 1.5, 1.5, 1, 1])
        
        c1.text(ma_sach)
        c2.text(ten_sach)
        c3.text(the_loai)
        c4.text(tac_gia)
        c5.text(nam_xb)
        
        if so_luong == 0:
            c6.markdown("<span style='color:red'>0</span>", unsafe_allow_html=True)
        else:
            c6.text(so_luong)

        if show_borrow_button:
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

if 'user_catalog_page' not in st.session_state:
    st.session_state.user_catalog_page = 1
if 'user_search_page' not in st.session_state:
    st.session_state.user_search_page = 1
if 'admin_manage_page' not in st.session_state:
    st.session_state.admin_manage_page = 1
if 'admin_search_page' not in st.session_state:
    st.session_state.admin_search_page = 1
if 'admin_user_page' not in st.session_state:
    st.session_state.admin_user_page = 1
if 'admin_loan_page' not in st.session_state:
    st.session_state.admin_loan_page = 1
if 'user_history_page' not in st.session_state:
    st.session_state.user_history_page = 1
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

def render_login_page():
    st.title("📚 Thư viện")
    tab_login, tab_reg = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký User"])

    with tab_login:
        role = st.radio("Bạn là:", ["Độc giả (User)", "Thủ thư (Admin)"], horizontal=True)
        if role == "Độc giả (User)":
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Đăng nhập"):
                sql = "SELECT MA_DG, HO_TEN, TRANG_THAI FROM NGUOI_DUNG WHERE USERNAME = :1 AND PASSWORD = :2"
                res, _ = execute_oracle(sql, [u, p])
                if res:
                    ma_dg, ho_ten, trang_thai = res[0]
                    if trang_thai == 1:
                        st.session_state.logged_in = True
                        st.session_state.role = "USER"
                        st.session_state.user_id = ma_dg
                        st.session_state.user_name = ho_ten
                        st.session_state.page = "catalog"
                        st.success(f"Chào mừng {ho_ten} quay trở lại!")
                        st.rerun()
                    else:
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
                    st.session_state.page = "catalog"
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
                new_ma_dg = get_next_id("NGUOI_DUNG", "MA_DG", "DG")
                sql = "INSERT INTO NGUOI_DUNG (MA_DG, USERNAME, PASSWORD, HO_TEN, SO_DIEN_THOAI) VALUES (:1, :2, :3, :4, :5)"
                success, err = execute_oracle(sql, [new_ma_dg, new_u, new_p, new_name, new_phone], is_select=False)
                if success:
                    if sync_user_node(new_ma_dg):
                        st.balloons()
                        st.success(f"Đăng ký thành công! Mã của bạn là: {new_ma_dg}")
                        st.info("Tài khoản đã được đồng bộ vào hệ thống gợi ý Graph.")
                    else:
                        st.warning("Đăng ký thành công nhưng không thể đồng bộ vào Neo4j.")
                else:
                    st.error(f"Lỗi Oracle: {err}")
            else:
                st.warning("Vui lòng điền đầy đủ các thông tin bắt buộc!")

if not st.session_state.get('logged_in', False):
    render_login_page()
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
        st.session_state.user_name = ""
        st.session_state.user_id = None
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
                    # Thứ tự xóa để tránh lỗi Constraint (Khóa ngoại) - dùng TRUNCATE cho tốc độ cao
                    queries = [
                        "TRUNCATE TABLE PHIEU_MUON",
                        "TRUNCATE TABLE SACH_TAC_GIA",
                        "TRUNCATE TABLE SACH",
                        "TRUNCATE TABLE THE_LOAI",
                        "TRUNCATE TABLE TAC_GIA",
                        "TRUNCATE TABLE NGUOI_DUNG"
                    ]
                    
                    success_all = True
                    for sql in queries:
                        status, err = execute_oracle(sql, is_select=False)
                        if status is None:
                            st.error(f"Lỗi Oracle: {err}")
                            success_all = False
                            break
                    
                    if success_all:
                        # Xóa trắng Neo4j nhanh hơn bằng batch delete từng loại node
                        try:
                            with GraphDatabase.driver(neo4j_uri, auth=neo4j_auth) as driver:
                                with driver.session() as session:
                                    # Xóa relationships trước
                                    session.run("MATCH ()-[r]-() DELETE r")
                                    # Xóa nodes theo loại
                                    session.run("MATCH (n:Book) DELETE n")
                                    session.run("MATCH (n:User) DELETE n")
                                    session.run("MATCH (n:Category) DELETE n")
                                    session.run("MATCH (n:Author) DELETE n")
                            st.success("Dữ liệu đã được làm sạch!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi Neo4j: {e}")
                    
                    # st.success("Dữ liệu đã được làm sạch!")
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
                            sync_book_node(ma_sach_ton_tai)
                    else:
                        # TRƯỜNG HỢP 2: Sách mới hoàn toàn -> Chèn mới với số lượng đã nhập
                        new_id = get_next_id("SACH", "MA_SACH", "S")
                        sql_book = "INSERT INTO SACH (MA_SACH, TEN_SACH, NAM_XB, MA_THE_LOAI, SO_LUONG) VALUES (:1, :2, :3, :4, :5)"
                        success_b, _ = execute_oracle(sql_book, [new_id, b_name, b_year, ma_tl, b_qty], is_select=False)
                        
                        # Chèn bảng trung gian tác giả
                        execute_oracle("INSERT INTO SACH_TAC_GIA (MA_SACH, MA_TG) VALUES (:1, :2)", [new_id, ma_tg], is_select=False)
                        
                        if success_b:
                            st.success(f"Thêm mới thành công! Mã sách: {new_id} với số lượng: {b_qty}")
                            sync_book_node(new_id)
                else:
                    st.warning("Vui lòng nhập đầy đủ tên sách, thể loại và tác giả!")
                        

        st.divider()
        st.subheader("📋 Chỉnh sửa / Xóa sách toàn diện")

        # 1. Bộ lọc tìm kiếm sách theo tên
        col_search, col_clear = st.columns([4, 1])
        with col_search:
            search_book = st.text_input("🔍 Tìm sách theo tên (VD: Python):", key="admin_search_book")
        with col_clear:
            if st.button("🔄 Xóa lọc", key="btn_clear_search"):
                st.session_state.admin_search_book = ""
                st.session_state.selected_book_id = None
                st.rerun()
        
        # 2. Lấy danh sách sách theo tìm kiếm bằng tên
        selected_id = None
        if search_book:
            res_manage, _ = query_books_page(page=1, page_size=10, ten_sach=search_book)
        else:
            # Nếu không tìm kiếm, chỉ lấy 10 sách đầu tiên (như cũ)
            res_manage, _ = query_books_page(page=1, page_size=10)
            
        if res_manage:
            book_dict = {
                row[0]: {
                    'name': row[1],
                    'cat': row[2],
                    'auth': row[3] if row[3] else "N/A",
                    'year': row[4],
                    'qty': row[5]
                } for row in res_manage
            }
            
            # Format options cho selectbox: "MA_SACH - Tên sách"
            book_options = [f"{bid} - {info['name'][:40]}" for bid, info in book_dict.items()]
            selected_option = st.selectbox(
                "Chọn mã sách cần xử lý:",
                options=book_options,
                key="admin_edit_selectbox"
            )
            # Lấy mã sách từ option được chọn (phần trước dấu " - ")
            selected_id = selected_option.split(" - ")[0] if selected_option else None
            
            if selected_id and selected_id in book_dict:
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
                        sync_book_node(selected_id)
                        st.rerun()

                    # --- XỬ LÝ XÓA ---
                    if submit_delete:
                        # Xóa theo thứ tự tránh lỗi Foreign Key Constraint:
                        # 1. Xóa các phiếu mượn
                        del_pm, err_pm = execute_oracle("DELETE FROM PHIEU_MUON WHERE MA_SACH = :1", [selected_id], is_select=False)
                        
                        # 2. Xóa tác giả liên kết
                        del_stg, err_stg = execute_oracle("DELETE FROM SACH_TAC_GIA WHERE MA_SACH = :1", [selected_id], is_select=False)
                        
                        # 3. Xóa sách
                        del_sach, err_sach = execute_oracle("DELETE FROM SACH WHERE MA_SACH = :1", [selected_id], is_select=False)
                        
                        if del_pm and del_stg and del_sach:
                            remove_book_from_neo4j(selected_id)
                            st.success(f"✅ Đã xóa hoàn toàn sách {selected_id} khỏi cơ sở dữ liệu!")
                            st.rerun()
                        else:
                            st.error(f"❌ Lỗi xóa sách: {err_pm or err_stg or err_sach}")
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

elif st.session_state.role == "USER":
    tab_main, tab_graph, tab_history_loan = st.tabs(["📚 Thư viện sách", "💡 Gợi ý cho bạn", "📖 Lịch sử mượn"])
    with tab_main:
        
        # Màn hình chính của Độc giả
        if st.session_state.page == "catalog":
            search_logic_user() # Luôn hiện bộ lọc ở trên cùng

            st.divider() # Vạch kẻ phân cách

            filters = st.session_state.get("user_search_filters")
            if filters:
                st.subheader("🎯 Kết quả tìm kiếm phù hợp")
                st.session_state.user_search_page = st.session_state.get("user_search_page", 1)
                page_size = PAGE_SIZE_SEARCH_ALL if is_search_all(filters) else PAGE_SIZE_DEFAULT
                rows, has_more = query_books_page(page=st.session_state.user_search_page,
                                                  page_size=page_size,
                                                  **filters)
                render_book_page(rows, st.session_state.user_search_page, has_more,
                                 prefix="search_res", state_key="user_search_page")
            else:
                st.subheader("📋 Danh mục sách chi tiết")
                if 'user_catalog_page' not in st.session_state:
                    st.session_state.user_catalog_page = 1
                rows, has_more = query_books_page(page=st.session_state.user_catalog_page, page_size=PAGE_SIZE_DEFAULT)
                render_book_page(rows, st.session_state.user_catalog_page, has_more,
                                 prefix="main_catalog", state_key="user_catalog_page")
        elif st.session_state.page == "borrow_detail":
            borrow_book_page()
    with tab_graph:
        display_recommendations()
    with tab_history_loan:
        display_user_borrow_history()