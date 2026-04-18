-- Chạy trên database đã tạo (ví dụ QuanNet) trong SSMS hoặc Azure Data Studio.
-- USE QuanNet;
-- GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        username   NVARCHAR(64)  NOT NULL PRIMARY KEY,
        password   NVARCHAR(256) NOT NULL,
        balance    DECIMAL(18, 2) NOT NULL CONSTRAINT DF_users_balance DEFAULT (0),
        user_type  NVARCHAR(16)  NOT NULL CONSTRAINT DF_users_type DEFAULT (N'normal')
    );
END
GO

IF OBJECT_ID(N'dbo.usage_history', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.usage_history (
        id           BIGINT IDENTITY(1, 1) NOT NULL PRIMARY KEY,
        username     NVARCHAR(64) NOT NULL,
        machine_id   INT NOT NULL,
        duration     FLOAT NOT NULL,
        recorded_at  DATETIME2(3) NOT NULL CONSTRAINT DF_usage_recorded DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_usage_users FOREIGN KEY (username) REFERENCES dbo.users (username) ON DELETE CASCADE
    );
    CREATE INDEX IX_usage_history_username ON dbo.usage_history (username);
END
GO

IF OBJECT_ID(N'dbo.menu_products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.menu_products (
        id            INT IDENTITY(1, 1) NOT NULL PRIMARY KEY,
        name          NVARCHAR(200) NOT NULL,
        price         DECIMAL(18, 2) NOT NULL CONSTRAINT DF_menu_products_price DEFAULT (0),
        is_active     BIT NOT NULL CONSTRAINT DF_menu_products_active DEFAULT (1),
        sort_order    INT NOT NULL CONSTRAINT DF_menu_products_sort DEFAULT (0),
        created_at    DATETIME2(3) NOT NULL CONSTRAINT DF_menu_products_created DEFAULT (SYSUTCDATETIME())
    );
    CREATE INDEX IX_menu_products_active ON dbo.menu_products (is_active);
END
GO

IF OBJECT_ID(N'dbo.orders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.orders (
        id           BIGINT IDENTITY(1, 1) NOT NULL PRIMARY KEY,
        machine_id   INT NOT NULL,
        ordered_at   DATETIME2(3) NOT NULL CONSTRAINT DF_orders_at DEFAULT (SYSUTCDATETIME()),
        summary_text NVARCHAR(MAX) NULL
    );
    CREATE INDEX IX_orders_machine ON dbo.orders (machine_id, ordered_at DESC);
END
GO

IF OBJECT_ID(N'dbo.order_items', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.order_items (
        id          BIGINT IDENTITY(1, 1) NOT NULL PRIMARY KEY,
        order_id    BIGINT NOT NULL,
        product_id  INT NOT NULL,
        qty         INT NOT NULL,
        unit_price  DECIMAL(18, 2) NOT NULL,
        CONSTRAINT CK_order_items_qty CHECK (qty > 0),
        CONSTRAINT FK_order_items_order FOREIGN KEY (order_id) REFERENCES dbo.orders (id) ON DELETE CASCADE,
        CONSTRAINT FK_order_items_product FOREIGN KEY (product_id) REFERENCES dbo.menu_products (id)
    );
    CREATE INDEX IX_order_items_order ON dbo.order_items (order_id);
END
GO