-- 股票大数据分析系统数据库初始化脚本
-- 数据库: 股票
-- 字符集: utf8

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS `股票` 
CHARACTER SET utf8 
COLLATE utf8_general_ci;

-- 使用数据库
USE `股票`;

-- 创建股票走势分析表
DROP TABLE IF EXISTS `股票走势分析`;

CREATE TABLE `股票走势分析` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `日期` DATE NOT NULL COMMENT '交易日期',
    `股票代码` VARCHAR(10) NOT NULL COMMENT '股票代码',
    `股票名称` VARCHAR(50) COMMENT '股票名称',
    `开盘价` DECIMAL(10, 2) COMMENT '开盘价格',
    `收盘价` DECIMAL(10, 2) COMMENT '收盘价格',
    `最高价` DECIMAL(10, 2) COMMENT '最高价格',
    `最低价` DECIMAL(10, 2) COMMENT '最低价格',
    `成交量` BIGINT COMMENT '成交量',
    `成交额` DECIMAL(15, 2) COMMENT '成交额',
    `涨跌幅` DECIMAL(10, 4) COMMENT '涨跌幅百分比',
    `换手率` DECIMAL(10, 4) COMMENT '换手率百分比',
    `MA5` DECIMAL(10, 2) COMMENT '5日移动平均线',
    `MA10` DECIMAL(10, 2) COMMENT '10日移动平均线',
    `MA20` DECIMAL(10, 2) COMMENT '20日移动平均线',
    `VOL_MA5` BIGINT COMMENT '5日成交量平均',
    `Momentum_5` DECIMAL(10, 4) COMMENT '5日价格动量',
    `价格波动` DECIMAL(10, 2) COMMENT '价格波动范围',
    `振幅` DECIMAL(10, 4) COMMENT '振幅百分比',
    `星期` TINYINT COMMENT '星期几(0-6)',
    `月份` TINYINT COMMENT '月份',
    `年份` SMALLINT COMMENT '年份',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_date` (`日期`),
    INDEX `idx_stock_code` (`股票代码`),
    INDEX `idx_stock_name` (`股票名称`),
    UNIQUE KEY `uk_date_stock` (`日期`, `股票代码`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COMMENT='股票走势分析表';

-- 查询表结构
DESCRIBE `股票走势分析`;

-- 查询示例数据（初始为空）
SELECT * FROM `股票走势分析` LIMIT 10;
