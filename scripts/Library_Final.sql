-- 1. Thể loại
CREATE TABLE THE_LOAI (
    ma_the_loai VARCHAR2(10) PRIMARY KEY,
    ten_the_loai NVARCHAR2(100) NOT NULL
);

-- 2. Tác giả 
CREATE TABLE TAC_GIA (
    ma_tg VARCHAR2(10) PRIMARY KEY,
    ten_tg NVARCHAR2(100) NOT NULL
);

-- 3. Sách
CREATE TABLE SACH (
    ma_sach VARCHAR2(10) PRIMARY KEY,
    ten_sach NVARCHAR2(200) NOT NULL,
    nam_xb NUMBER(4),
    ma_the_loai VARCHAR2(10),
    so_luong NUMBER DEFAULT 1,
    CONSTRAINT fk_sach_theloai FOREIGN KEY (ma_the_loai) REFERENCES THE_LOAI(ma_the_loai)
);

-- 4. Bảng trung gian Sách - Tác giả
CREATE TABLE SACH_TAC_GIA (
    ma_sach VARCHAR2(10),
    ma_tg VARCHAR2(10),
    PRIMARY KEY (ma_sach, ma_tg),
    CONSTRAINT fk_stg_sach FOREIGN KEY (ma_sach) REFERENCES SACH(ma_sach),
    CONSTRAINT fk_stg_tg FOREIGN KEY (ma_tg) REFERENCES TAC_GIA(ma_tg)
);

-- 5. Người dùng (Kết hợp chặt chẽ mã quản lý và tên đăng nhập)
CREATE TABLE NGUOI_DUNG (
    ma_dg VARCHAR2(20) PRIMARY KEY, -- Mã dùng để quản lý (Ví dụ: DG001)
    username VARCHAR2(50) UNIQUE NOT NULL, -- Dùng để đăng nhập
    password VARCHAR2(255) NOT NULL,
    ho_ten NVARCHAR2(100) NOT NULL,
    so_dien_thoai VARCHAR2(15),
    trang_thai NUMBER(1) DEFAULT 1
);

-- 6. Phiếu mượn (Quản lý theo mã độc giả)
CREATE TABLE PHIEU_MUON (
    ma_pm VARCHAR2(10) PRIMARY KEY,
    ma_dg VARCHAR2(20), -- Liên kết qua mã quản lý
    ma_sach VARCHAR2(10),
    so_luong_muon NUMBER DEFAULT 1,
    ngay_tra_du_kien DATE,
    ngay_tra_thuc_te DATE,
    ghi_chu_admin NVARCHAR2(500),
    trang_thai NVARCHAR2(50) DEFAULT 'Đang mượn', -- Đang mượn, Đã trả
    ngay_muon DATE DEFAULT SYSDATE,
    CONSTRAINT fk_pm_dg FOREIGN KEY (ma_dg) REFERENCES NGUOI_DUNG(ma_dg),
    CONSTRAINT fk_pm_sach FOREIGN KEY (ma_sach) REFERENCES SACH(ma_sach)
);


-- Chỉ bôi đen dòng này và nhấn Explain Plan
INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong)
VALUES ('S001', N'Sách chuyên ngành', 2024, 'TL_CN', 10);
COMMIT;
-- Sau đó chạy dòng này để xem kết quả chi tiết
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

-- Thêm thể loại nếu là loại mới
INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) 
VALUES ('TL004', N'Khoa học viễn tưởng');

-- Thêm tác giả nếu là tác giả mới
INSERT INTO TAC_GIA (ma_tg, ten_tg) 
VALUES ('TG004', N'Jules Verne');

INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong)
VALUES ('S004', N'Hai vạn dặm dưới đáy biển', 1870, 'TL004', 10);

INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) 
VALUES ('S004', 'TG004');

COMMIT; -- Lưu thay đổi vĩnh viễn

EXPLAIN PLAN FOR
SELECT s.ten_sach, tg.ten_tg
FROM SACH s
JOIN SACH_TAC_GIA stg ON s.ma_sach = stg.ma_sach
JOIN TAC_GIA tg ON stg.ma_tg = tg.ma_tg
WHERE s.ma_sach = 'S004';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

-- Bật đo thời gian (Dành cho Người 3)
SET TIMING ON;

SELECT DISTINCT tg.ten_tg
FROM SACH s1
JOIN THE_LOAI tl ON s1.ma_the_loai = tl.ma_the_loai
JOIN SACH s2 ON tl.ma_the_loai = s2.ma_the_loai
JOIN SACH_TAC_GIA stg ON s2.ma_sach = stg.ma_sach
JOIN TAC_GIA tg ON stg.ma_tg = tg.ma_tg
WHERE s1.ma_sach = 'S004' AND tg.ten_tg <> (
    -- Loại trừ tác giả của chính cuốn sách đó
    SELECT ten_tg FROM TAC_GIA tg2 
    JOIN SACH_TAC_GIA stg2 ON tg2.ma_tg = stg2.ma_tg 
    WHERE stg2.ma_sach = 'S004'
);


-- 1. Thêm Thể loại chung
INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) 
VALUES ('TL_KH', N'Khoa học');

-- 2. Thêm 2 Tác giả khác nhau
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG_01', N'Jules Verne');
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG_02', N'Stephen Hawking');

-- 3. Thêm 2 cuốn sách cùng thể loại TL_KH
-- Cuốn S004 (bạn đã làm)
INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong)
VALUES ('S004', N'Hai vạn dặm dưới đáy biển', 1870, 'TL_KH', 10);

-- Cuốn sách khác cùng thể loại để test gợi ý
INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong)
VALUES ('S_TEST', N'Lược sử thời gian', 1988, 'TL_KH', 5);

-- 4. Liên kết Sách với Tác giả
INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES ('S004', 'TG_01');
INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES ('S_TEST', 'TG_02');

COMMIT;

EXPLAIN PLAN FOR
SELECT DISTINCT tg.ten_tg
FROM SACH s1
JOIN SACH s2 ON s1.ma_the_loai = s2.ma_the_loai
JOIN SACH_TAC_GIA stg ON s2.ma_sach = stg.ma_sach
JOIN TAC_GIA tg ON stg.ma_tg = tg.ma_tg
WHERE s1.ma_sach = 'S004' AND s2.ma_sach <> 'S004';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

-- Thêm thể loại và tác giả mẫu nếu bạn chưa có
INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) VALUES ('TL_KH', N'Khoa học');
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG_01', N'Tác giả A');
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG_02', N'Tác giả B');
COMMIT;

DECLARE
    v_ma_sach VARCHAR2(10);
BEGIN
    FOR i IN 1..10000 LOOP
        v_ma_sach := 'B_' || i; -- Mã sách tối đa 10 ký tự theo khai báo của bạn
        
        -- 1. Nạp vào bảng SACH
        INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong)
        VALUES (v_ma_sach, N'Sách kiểm thử hiệu năng số ' || i, 2024, 'TL_KH', 5);
        
        -- 2. Nạp vào bảng trung gian SACH_TAC_GIA
        -- Chia đều sách cho 2 tác giả để tạo độ phức tạp khi truy vấn
        IF MOD(i, 2) = 0 THEN
            INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES (v_ma_sach, 'TG_01');
        ELSE
            INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES (v_ma_sach, 'TG_02');
        END IF;

        -- Commit sau mỗi 1000 dòng để tối ưu bộ nhớ đệm
        IF MOD(i, 1000) = 0 THEN
            COMMIT;
        END IF;
    END LOOP;
    COMMIT;
END;

SET TIMING ON;
SELECT DISTINCT tg.ten_tg
FROM SACH s1
JOIN SACH s2 ON s1.ma_the_loai = s2.ma_the_loai
JOIN SACH_TAC_GIA stg ON s2.ma_sach = stg.ma_sach
JOIN TAC_GIA tg ON stg.ma_tg = tg.ma_tg
WHERE s1.ma_sach = 'B_5000';
-- Ghi lại số giây (Elapsed: 00:00:00.XXX)

CREATE INDEX idx_sach_theloai ON SACH(ma_the_loai);
DROP INDEX idx_sach_theloai;
DROP INDEX index_book_id IF EXISTS;
EXPLAIN PLAN FOR
SELECT * FROM SACH WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);
DECLARE
    v_ma_sach VARCHAR2(10);
BEGIN
    -- 1. Đảm bảo có dữ liệu nền cho khóa ngoại
    INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) VALUES ('TL_KH', N'Khoa học');
    INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG_01', N'Tác giả A');
    INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG_02', N'Tác giả B');
    COMMIT;

    -- 2. Nạp 50,000 cuốn sách test
    FOR i IN 1..50000 LOOP
        v_ma_sach := 'B_' || i; 
        
        INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong)
        VALUES (v_ma_sach, N'Sách Test Hiệu Năng ' || i, 2026, 'TL_KH', 10);
        
        -- Gán quan hệ Sách - Tác giả
        IF MOD(i, 2) = 0 THEN
            INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES (v_ma_sach, 'TG_01');
        ELSE
            INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES (v_ma_sach, 'TG_02');
        END IF;

        IF MOD(i, 5000) = 0 THEN COMMIT; END IF;
    END LOOP;
    COMMIT;
END;
SELECT DISTINCT tg.ten_tg
FROM SACH s1
JOIN SACH s2 ON s1.ma_the_loai = s2.ma_the_loai
JOIN SACH_TAC_GIA stg ON s2.ma_sach = stg.ma_sach
JOIN TAC_GIA tg ON stg.ma_tg = tg.ma_tg
WHERE s1.ma_sach = 'B_25000';

DROP INDEX idx_sach_theloai;
SET TIMING ON;
EXPLAIN PLAN FOR
SELECT DISTINCT tg.ten_tg FROM SACH s1 
JOIN SACH s2 ON s1.ma_the_loai = s2.ma_the_loai 
JOIN SACH_TAC_GIA stg ON s2.ma_sach = stg.ma_sach 
JOIN TAC_GIA tg ON stg.ma_tg = tg.ma_tg 
WHERE s1.ma_sach = 'B_25000';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

SET TIMING ON;
EXPLAIN PLAN FOR
SELECT * FROM SACH WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

CREATE INDEX idx_sach_theloai ON SACH(ma_the_loai);
CREATE INDEX idx_theloai_range ON SACH(ma_the_loai);
EXPLAIN PLAN FOR
SELECT * FROM SACH WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);
EXPLAIN PLAN FOR
SELECT /*+ INDEX(SACH idx_theloai_range) */ * FROM SACH 
WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);
CREATE INDEX idx_sach_theloai_test ON SACH(ma_the_loai);
EXPLAIN PLAN FOR
SELECT /*+ INDEX(SACH idx_sach_theloai_test) */ * FROM SACH 
WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

-- Xóa nếu tên này đã lỡ tồn tại từ trước
DROP INDEX idx_test_range;

-- Tạo mới index trên cột Thể loại
CREATE INDEX idx_test_range ON SACH(ma_the_loai);
CREATE INDEX idx_theloai_chuan ON SACH(ma_the_loai);
SELECT index_name 
FROM user_ind_columns 
WHERE table_name = 'SACH' AND column_name = 'MA_THE_LOAI';

EXPLAIN PLAN FOR
SELECT /*+ INDEX(SACH IDX_SACH_THELOAI) */ * FROM SACH 
WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

DROP INDEX IDX_SACH_THELOAI;

EXPLAIN PLAN FOR
SELECT * FROM SACH 
WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

CREAT INDEX IDX_SACH_THELOAI;
EXPLAIN PLAN FOR
SELECT /*+ FULL(SACH) */ * FROM SACH 
WHERE ma_the_loai = 'TL_KH';

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);
EXEC DBMS_STATS.GATHER_TABLE_STATS(USER, 'SACH');


-- 1. Dữ liệu mẫu Thể loại
INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) VALUES ('TL001', N'Khoa học máy tính');
INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) VALUES ('TL002', N'Kỹ thuật điện tử');
INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) VALUES ('TL003', N'Kinh tế');

-- 2. Dữ liệu mẫu Tác giả
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG001', N'Nguyễn Văn A');
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG002', N'Trần Thị B');
INSERT INTO TAC_GIA (ma_tg, ten_tg) VALUES ('TG003', N'James Smith');

-- 3. Dữ liệu mẫu Sách
INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong) 
VALUES ('S001', N'Lập trình ESP32 với FreeRTOS', 2023, 'TL001', 15);
INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong) 
VALUES ('S002', N'Thiết kế mạch VLSI cơ bản', 2022, 'TL002', 10);
INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong) 
VALUES ('S003', N'Cấu trúc dữ liệu và Giải thuật', 2024, 'TL001', 5);

-- 4. Liên kết Sách - Tác giả (Bảng trung gian)
INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES ('S001', 'TG001');
INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES ('S001', 'TG003'); -- Sách S001 có 2 tác giả
INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES ('S002', 'TG002');
INSERT INTO SACH_TAC_GIA (ma_sach, ma_tg) VALUES ('S003', 'TG001');


-- 5. Dữ liệu mẫu Người dùng
-- Lưu ý: Password nên được mã hóa nếu dùng thực tế, ở đây để text mẫu.
INSERT INTO NGUOI_DUNG (ma_dg, username, password, ho_ten, so_dien_thoai, trang_thai) 
VALUES ('DG001', 'sinhvien1', 'pass123', N'Lê Văn Thành', '0912345678', 1);
INSERT INTO NGUOI_DUNG (ma_dg, username, password, ho_ten, so_dien_thoai, trang_thai) 
VALUES ('DG002', 'sinhvien2', 'pass456', N'Nguyễn Minh Thư', '0987654321', 1);

-- 6. Dữ liệu mẫu Phiếu mượn
-- Phiếu mượn 1: Đã trả (Có ngày trả thực tế)
INSERT INTO PHIEU_MUON (ma_pm, ma_dg, ma_sach, so_luong_muon, ngay_tra_du_kien, ngay_tra_thuc_te, trang_thai, ngay_muon) 
VALUES ('PM001', 'DG001', 'S001', 1, TO_DATE('2026-05-15', 'YYYY-MM-DD'), TO_DATE('2026-05-08', 'YYYY-MM-DD'), N'Đã trả', TO_DATE('2026-05-01', 'YYYY-MM-DD'));

-- Phiếu mượn 2: Đang mượn (Chưa có ngày trả thực tế)
INSERT INTO PHIEU_MUON (ma_pm, ma_dg, ma_sach, so_luong_muon, ngay_tra_du_kien, trang_thai, ngay_muon) 
VALUES ('PM002', 'DG002', 'S002', 1, TO_DATE('2026-05-20', 'YYYY-MM-DD'), N'Đang mượn', SYSDATE);

-- Phiếu mượn 3: Đang mượn quá hạn (Giả lập để test bộ lọc quá hạn)
INSERT INTO PHIEU_MUON (ma_pm, ma_dg, ma_sach, so_luong_muon, ngay_tra_du_kien, trang_thai, ngay_muon) 
VALUES ('PM003', 'DG001', 'S003', 1, TO_DATE('2026-05-05', 'YYYY-MM-DD'), N'Đang mượn', TO_DATE('2026-04-25', 'YYYY-MM-DD'));

COMMIT;


CREATE INDEX idx_sach_ten_upper ON SACH (UPPER(ten_sach));
CREATE INDEX idx_sach_theloai ON SACH (ma_the_loai);
CREATE INDEX idx_pm_madg ON PHIEU_MUON (ma_dg);
CREATE INDEX idx_pm_trangthai ON PHIEU_MUON (trang_thai);
CREATE INDEX idx_pm_ngaymuon ON PHIEU_MUON (ngay_muon DESC);
CREATE INDEX idx_nd_hoten_upper ON NGUOI_DUNG (UPPER(ho_ten));
CREATE INDEX idx_stg_matg ON SACH_TAC_GIA (ma_tg);
EXPLAIN PLAN FOR
SELECT * FROM SACH 
WHERE UPPER(TEN_SACH) LIKE 'PYTHON%';
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY);

-- Tạo 20 thể loại
BEGIN
  FOR i IN 1..20 LOOP
    INSERT INTO THE_LOAI (ma_the_loai, ten_the_loai) 
    VALUES ('TL' || LPAD(i, 3, '0'), N'Thể loại mẫu số ' || i);
  END LOOP;
  
  -- Tạo 1000 tác giả
  FOR i IN 1..1000 LOOP
    INSERT INTO TAC_GIA (ma_tg, ten_tg) 
    VALUES ('TG' || LPAD(i, 4, '0'), N'Tác giả chuyên nghiệp ' || i);
  END LOOP;
  COMMIT;
END;
/

BEGIN
  FOR i IN 1..50000 LOOP
    INSERT INTO SACH (ma_sach, ten_sach, nam_xb, ma_the_loai, so_luong) 
    VALUES (
      'S' || LPAD(i, 5, '0'), -- Tạo mã kiểu S00001, S00002...
      N'Sách lập trình hệ thống tập ' || i || ' ' || DBMS_RANDOM.STRING('U', 5), 
      TRUNC(DBMS_RANDOM.VALUE(2000, 2026)), -- Năm XB từ 2000 đến 2026
      'TL' || LPAD(TRUNC(DBMS_RANDOM.VALUE(1, 21)), 3, '0'), -- Ngẫu nhiên 1 trong 20 thể loại
      TRUNC(DBMS_RANDOM.VALUE(1, 100)) -- Số lượng trong kho từ 1-100
    );
    
    -- Cứ 1000 dòng thì Commit một lần để tránh treo bộ nhớ log
    IF MOD(i, 1000) = 0 THEN
      COMMIT;
    END IF;
  END LOOP;
  COMMIT;
END;
/



BEGIN
  -- Tạo 1000 người dùng
  FOR i IN 1..1000 LOOP
    INSERT INTO NGUOI_DUNG (ma_dg, username, password, ho_ten, so_dien_thoai, trang_thai)
    VALUES (
      'DG' || LPAD(i, 4, '0'),
      'user' || i,
      'password' || i,
      N'Sinh viên Bách Khoa ' || i,
      '09' || LPAD(i, 8, '0'),
      1
    );
  END LOOP;

  -- Tạo 20.000 phiếu mượn ngẫu nhiên
  FOR i IN 1..20000 LOOP
    INSERT INTO PHIEU_MUON (
        ma_pm, 
        ma_dg, 
        ma_sach, 
        so_luong_muon, 
        ngay_muon, 
        ngay_tra_du_kien, -- Đã sửa: bỏ dấu 'ê' thành 'e'
        trang_thai
    )
    VALUES (
      'PM' || LPAD(i, 5, '0'),
      'DG' || LPAD(TRUNC(DBMS_RANDOM.VALUE(1, 1001)), 4, '0'),
      'S' || LPAD(TRUNC(DBMS_RANDOM.VALUE(1, 50001)), 5, '0'),
      1,
      SYSDATE - DBMS_RANDOM.VALUE(1, 100), 
      SYSDATE + DBMS_RANDOM.VALUE(1, 14),  
      CASE WHEN DBMS_RANDOM.VALUE > 0.5 THEN N'Đã trả' ELSE N'Đang mượn' END
    );
    
    IF MOD(i, 1000) = 0 THEN COMMIT; END IF;
  END LOOP;
  COMMIT;
END;
/

SELECT * FROM NGUOI_DUNG;
SELECT * FROM SACH;
SELECT * FROM THE_LOAI;
SELECT * FROM TAC_GIA;
SELECT * FROM PHIEU_MUON;