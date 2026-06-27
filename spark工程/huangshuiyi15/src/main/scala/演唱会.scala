package org.example

import java.io.{File, PrintWriter}
import java.sql.{Connection, DriverManager}
import scala.io.Source

case class Concert(
  id: String, title: String, singer: String, popularity: Int, genre: String,
  province: String, city: String, venue: String, venueType: String, capacity: Int,
  startDate: String, endDate: String, duration: Int, platform: String,
  minPrice: Int, maxPrice: Int, attendance: Int, ticketStatus: String
)

object ConcertAnalysis {

  val DB_URL = "jdbc:mysql://localhost:3306?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true"
  val DB_USER = "root"
  val DB_PASS = "321321"
  val GD_CITIES = Set("广州", "深圳", "珠海", "汕头", "佛山", "韶关", "湛江", "肇庆", "江门",
    "茂名", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮")

  def main(args: Array[String]): Unit = {
    println("=" * 80)
    println("              全国演唱会数据分析系统")
    println("=" * 80)

    val concerts = loadConcerts("singdata.csv")
    println(s"\n  共加载 ${concerts.size} 条演唱会数据\n")

    println("=" * 80)
    println("[1] 歌手演唱会统计排名")
    println("=" * 80)
    singerAnalysis(concerts)

    println("\n" + "=" * 80)
    println("[2] 广东省演唱会专题分析")
    println("=" * 80)
    val gdConcerts = guangdongAnalysis(concerts)

    println("\n" + "=" * 80)
    println("[3] 喜爱的歌手演唱会信息 (周杰伦)")
    println("=" * 80)
    val favConcerts = favoriteSingerAnalysis(concerts, "周杰伦")

    println("\n" + "=" * 80)
    println("[4] 扩展统计分析")
    println("=" * 80)
    extendedAnalysis(concerts)

    println("\n" + "=" * 80)
    println("[5] 导出CSV文件")
    println("=" * 80)
    exportCSV(gdConcerts, "广东省演唱会数据.csv", "gd_vc")
    exportCSV(favConcerts, "周杰伦演唱会数据.csv", "singer")

    println("\n" + "=" * 80)
    println("[6] 录入MySQL数据库")
    println("=" * 80)
    saveToMySQL(gdConcerts, favConcerts)
  }

  // ==================== 数据加载 ====================

  def loadConcerts(resource: String): List[Concert] = {
    var stream = getClass.getClassLoader.getResourceAsStream(resource)
    if (stream == null) stream = getClass.getResourceAsStream("/" + resource)
    if (stream == null) {
      println(s"  错误: 未找到资源文件 $resource")
      return List.empty
    }
    val source = Source.fromInputStream(stream, "UTF-8")
    val lines = source.mkString.split("\n").map(_.trim).filter(_.nonEmpty).toList
    source.close()
    val cleanLines = if (lines.head.startsWith("\ufeff")) lines.head.tail :: lines.tail else lines
    cleanLines.tail.flatMap(parseLine)
  }

  def parseLine(line: String): Option[Concert] = {
    val f = line.split(",", -1)
    if (f.length < 18) return None
    try {
      Some(Concert(
        f(0).trim, f(1).trim, f(2).trim, f(3).trim.toInt, f(4).trim,
        f(5).trim, f(6).trim, f(7).trim, f(8).trim, f(9).trim.toInt,
        f(10).trim, f(11).trim, f(12).trim.toInt, f(13).trim,
        f(14).trim.toInt, f(15).trim.toInt, f(16).trim.toInt, f(17).trim
      ))
    } catch { case _: Exception => None }
  }

  // ==================== [1] 歌手统计分析 ====================

  def singerAnalysis(concerts: List[Concert]): Unit = {
    val grouped = concerts.groupBy(_.singer)
    val stats = grouped.map { case (singer, list) =>
      val venueSet = list.map(_.venue).toSet
      (singer, list.size, venueSet.size,
        list.map(_.popularity).sum.toDouble / list.size,
        list.map(_.maxPrice).sum.toDouble / list.size,
        list.map(_.attendance).sum)
    }.toList.sortBy(-_._2)

    println(f"\n  ${"排名"}%-4s ${"歌手"}%-14s ${"场数"}%6s ${"场馆数"}%8s ${"平均热度"}%10s ${"平均票价"}%10s ${"总入场"}%12s")
    println("  " + "-" * 78)
    stats.zipWithIndex.foreach { case ((singer, count, venues, pop, price, attend), idx) =>
      println(f"  ${idx + 1}%-4d $singer%-14s $count%6d $venues%8d $pop%10.1f $price%10.0f $attend%12d")
    }
    println(f"\n  共 ${stats.size} 位歌手, ${concerts.size} 场演唱会")
  }

  // ==================== [2] 广东省分析 ====================

  def guangdongAnalysis(concerts: List[Concert]): List[Concert] = {
    val gd = concerts.filter(c => c.province == "广东" || GD_CITIES.contains(c.city))
    println(s"\n  广东省演唱会总数: ${gd.size} 场")

    // 按年份统计
    val byYear = gd.groupBy(c => c.startDate.take(4)).toList.sortBy(_._1)
    println(f"\n  ${"年份"}%-8s ${"场数"}%6s ${"平均热度"}%10s ${"平均票价"}%10s ${"总入场"}%12s")
    println("  " + "-" * 55)
    byYear.foreach { case (year, list) =>
      println(f"  $year%-8s ${list.size}%6d ${list.map(_.popularity).sum.toDouble / list.size}%10.1f ${list.map(_.maxPrice).sum.toDouble / list.size}%10.0f ${list.map(_.attendance).sum}%12d")
    }

    // 按城市统计
    val byCity = gd.groupBy(_.city).toList.sortBy(-_._2.size)
    println(f"\n  ${"城市"}%-10s ${"场数"}%6s ${"平均热度"}%10s ${"平均票价"}%10s ${"总入场"}%12s")
    println("  " + "-" * 55)
    byCity.foreach { case (city, list) =>
      println(f"  $city%-10s ${list.size}%6d ${list.map(_.popularity).sum.toDouble / list.size}%10.1f ${list.map(_.maxPrice).sum.toDouble / list.size}%10.0f ${list.map(_.attendance).sum}%12d")
    }

    // 广东省热门歌手
    val topSingers = gd.groupBy(_.singer).map { case (s, l) => (s, l.size) }.toList.sortBy(-_._2).take(10)
    println(f"\n  广东省热门歌手 TOP10:")
    println("  " + "-" * 35)
    topSingers.zipWithIndex.foreach { case ((singer, count), idx) =>
      println(f"  ${idx + 1}. $singer%-14s ${count}场")
    }
    gd
  }

  // ==================== [3] 喜爱歌手分析 ====================

  def favoriteSingerAnalysis(concerts: List[Concert], name: String): List[Concert] = {
    val fav = concerts.filter(_.singer == name).sortBy(_.startDate)
    if (fav.isEmpty) {
      println(s"  未找到歌手 '$name' 的演唱会数据")
      return List.empty
    }
    println(s"\n  歌手: $name")
    println(s"  演唱会总数: ${fav.size} 场")
    println(s"  平均热度: ${fav.map(_.popularity).sum.toDouble / fav.size}%.1f")
    println(s"  平均票价: ${fav.map(_.maxPrice).sum.toDouble / fav.size}%.0f 元")
    println(s"  总入场人数: ${fav.map(_.attendance).sum}")

    // 按年份分布
    val byYear = fav.groupBy(c => c.startDate.take(4)).toList.sortBy(_._1)
    println(f"\n  ${"年份"}%-8s ${"场数"}%6s ${"平均热度"}%10s ${"主要城市"}%s")
    println("  " + "-" * 60)
    byYear.foreach { case (year, list) =>
      val cities = list.groupBy(_.city).map { case (c, l) => s"$c(${l.size})" }.mkString(", ")
      println(f"  $year%-8s ${list.size}%6d ${list.map(_.popularity).sum.toDouble / list.size}%10.1f   $cities")
    }

    // 详细列表
    println(f"\n  ${"序号"}%-4s ${"日期"}%-12s ${"城市"}%-8s ${"场馆"}%-28s ${"热度"}%6s ${"票价"}%8s ${"入场"}%8s")
    println("  " + "-" * 85)
    fav.zipWithIndex.foreach { case (c, idx) =>
      println(f"  ${idx + 1}%-4d ${c.startDate}%-12s ${c.city}%-8s ${c.venue}%-28s ${c.popularity}%6d ${c.maxPrice}%8d ${c.attendance}%8d")
    }
    fav
  }

  // ==================== [4] 扩展分析 ====================

  def extendedAnalysis(concerts: List[Concert]): Unit = {
    // 4.1 票价与售票关系
    println("\n  === 4.1 票价与售票关系 ===")
    val priceGroups = List(
      ("低价(<100)", concerts.filter(_.maxPrice < 100)),
      ("中低(100-199)", concerts.filter(c => c.maxPrice >= 100 && c.maxPrice < 200)),
      ("中高(200-299)", concerts.filter(c => c.maxPrice >= 200 && c.maxPrice < 300)),
      ("高价(>=300)", concerts.filter(_.maxPrice >= 300))
    )
    println(f"  ${"价位段"}%-18s ${"场数"}%6s ${"平均入场"}%10s ${"平均上座率"}%12s ${"余票较多"}%10s")
    println("  " + "-" * 65)
    priceGroups.foreach { case (label, list) =>
      if (list.nonEmpty) {
        val avgAttend = list.map(_.attendance).sum.toDouble / list.size
        val avgRate = list.map(c => c.attendance.toDouble / c.capacity * 100).sum / list.size
        val surplus = list.count(_.ticketStatus.contains("余票"))
        println(f"  $label%-18s ${list.size}%6d $avgAttend%10.0f $avgRate%10.1f%% $surplus%10d")
      }
    }

    // 4.2 艺人热度分析
    println("\n  === 4.2 艺人热度与演唱会规模关系 ===")
    val popGroups = List(
      ("低热度(<60)", concerts.filter(_.popularity < 60)),
      ("中热度(60-79)", concerts.filter(c => c.popularity >= 60 && c.popularity < 80)),
      ("高热度(80-89)", concerts.filter(c => c.popularity >= 80 && c.popularity < 90)),
      ("超高热度(>=90)", concerts.filter(_.popularity >= 90))
    )
    println(f"  ${"热度段"}%-18s ${"场数"}%6s ${"平均场馆"}%10s ${"平均票价"}%10s ${"平均入场"}%10s")
    println("  " + "-" * 60)
    popGroups.foreach { case (label, list) =>
      if (list.nonEmpty) {
        val avgCap = list.map(_.capacity).sum.toDouble / list.size
        val avgPrice = list.map(_.maxPrice).sum.toDouble / list.size
        val avgAttend = list.map(_.attendance).sum.toDouble / list.size
        println(f"  $label%-18s ${list.size}%6d $avgCap%10.0f $avgPrice%10.0f $avgAttend%10.0f")
      }
    }

    // 4.3 淡季旺季分析
    println("\n  === 4.3 演唱会淡旺季分析 ===")
    val monthly = concerts.groupBy(c => c.startDate.substring(5, 7).toInt).toList.sortBy(_._1)
    println(f"  ${"月份"}%-6s ${"场数"}%6s ${"平均热度"}%10s ${"平均票价"}%10s ${"分布"}%s")
    println("  " + "-" * 70)
    val maxMonthly = monthly.map(_._2.size).max
    monthly.foreach { case (month, list) =>
      val barLen = (list.size.toDouble / maxMonthly * 30).toInt
      val bar = "█" * barLen
      println(f"  ${month + "月"}%-6s ${list.size}%6d ${list.map(_.popularity).sum.toDouble / list.size}%10.1f ${list.map(_.maxPrice).sum.toDouble / list.size}%10.0f  $bar")
    }
    val peakMonths = monthly.sortBy(-_._2.size).take(3).map(_._1)
    val lowMonths = monthly.sortBy(_._2.size).take(3).map(_._1)
    println(s"\n  >>> 旺季月份: ${peakMonths.mkString(", ")}月")
    println(s"  >>> 淡季月份: ${lowMonths.mkString(", ")}月")

    // 4.4 场馆类型分析
    println("\n  === 4.4 场馆类型统计 ===")
    val venueTypes = concerts.groupBy(_.venueType).map { case (vt, list) =>
      (vt, list.size, list.map(_.capacity).sum.toDouble / list.size, list.map(_.attendance).sum)
    }.toList.sortBy(-_._2)
    println(f"  ${"场馆类型"}%-12s ${"场数"}%6s ${"平均容纳"}%10s ${"总入场"}%12s")
    println("  " + "-" * 50)
    venueTypes.foreach { case (vt, count, avgCap, total) =>
      println(f"  $vt%-12s $count%6d $avgCap%10.0f $total%12d")
    }
  }

  // ==================== [5] CSV导出 ====================

  def exportCSV(data: List[Concert], filename: String, label: String): Unit = {
    val writer = new PrintWriter(new File(filename))
    writer.print('\ufeff')
    writer.println("演唱会ID,名称,歌手,热度,风格,省份,城市,场馆,场馆类型,容纳量,开始日期,结束日期,时长,平台,票价下限,票价上限,入场人数,售票状态")
    data.foreach { c =>
      writer.println(s"${c.id},${c.title},${c.singer},${c.popularity},${c.genre},${c.province},${c.city},${c.venue},${c.venueType},${c.capacity},${c.startDate},${c.endDate},${c.duration},${c.platform},${c.minPrice},${c.maxPrice},${c.attendance},${c.ticketStatus}")
    }
    writer.close()
    println(s"  已导出 [$label]: $filename (${data.size} 条记录)")
  }

  // ==================== [6] MySQL数据库操作 ====================

  def saveToMySQL(gdConcerts: List[Concert], favConcerts: List[Concert]): Unit = {
    var conn: Connection = null
    try {
      Class.forName("com.mysql.cj.jdbc.Driver")
      conn = DriverManager.getConnection(DB_URL, DB_USER, DB_PASS)
      println("  MySQL连接成功!")

      // 创建数据库 gd_vc
      executeUpdate(conn, "CREATE DATABASE IF NOT EXISTS gd_vc DEFAULT CHARACTER SET utf8mb4")
      println("  数据库 gd_vc 创建/确认成功")

      // 创建数据库 singer
      executeUpdate(conn, "CREATE DATABASE IF NOT EXISTS singer DEFAULT CHARACTER SET utf8mb4")
      println("  数据库 singer 创建/确认成功")

      // 广东省数据录入 gd_vc
      saveGdToMySQL(gdConcerts)
      // 喜爱歌手数据录入 singer
      saveSingerToMySQL(favConcerts)

      println("\n  数据库录入完成!")
    } catch {
      case e: ClassNotFoundException =>
        println(s"  MySQL驱动未找到: ${e.getMessage}")
        println("  请确保已添加 mysql-connector-j 依赖并刷新Maven")
      case e: java.sql.SQLException =>
        println(s"  MySQL连接失败: ${e.getMessage}")
        println("  请确保MySQL服务已启动，并检查用户名密码配置")
        println(s"  当前配置: URL=$DB_URL, USER=$DB_USER")
      case e: Exception =>
        println(s"  数据库操作异常: ${e.getMessage}")
        e.printStackTrace()
    } finally {
      if (conn != null) try { conn.close() } catch { case _: Exception => }
    }
  }

  def executeUpdate(conn: Connection, sql: String): Unit = {
    val stmt = conn.createStatement()
    try { stmt.executeUpdate(sql) } finally { stmt.close() }
  }

  def saveGdToMySQL(gdConcerts: List[Concert]): Unit = {
    val conn = DriverManager.getConnection(
      "jdbc:mysql://localhost:3306/gd_vc?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true",
      DB_USER, DB_PASS)
    try {
      // 创建表
      val createSQL =
        """CREATE TABLE IF NOT EXISTS gd_concert (
          |  id VARCHAR(20) PRIMARY KEY,
          |  title VARCHAR(200), singer VARCHAR(50), popularity INT,
          |  genre VARCHAR(50), province VARCHAR(20), city VARCHAR(20),
          |  venue VARCHAR(100), venue_type VARCHAR(30), capacity INT,
          |  start_date VARCHAR(20), end_date VARCHAR(20), duration INT,
          |  platform VARCHAR(50), min_price INT, max_price INT,
          |  attendance INT, ticket_status VARCHAR(50)
          |) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""".stripMargin
      executeUpdate(conn, createSQL)
      println(s"  gd_vc.gd_concert 表创建/确认成功")

      // 插入数据
      val insertSQL =
        """INSERT INTO gd_concert (id,title,singer,popularity,genre,province,city,venue,venue_type,capacity,start_date,end_date,duration,platform,min_price,max_price,attendance,ticket_status)
          |VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          |ON DUPLICATE KEY UPDATE title=VALUES(title), attendance=VALUES(attendance)""".stripMargin

      val ps = conn.prepareStatement(insertSQL)
      var count = 0
      gdConcerts.foreach { c =>
        ps.setString(1, c.id); ps.setString(2, c.title); ps.setString(3, c.singer)
        ps.setInt(4, c.popularity); ps.setString(5, c.genre); ps.setString(6, c.province)
        ps.setString(7, c.city); ps.setString(8, c.venue); ps.setString(9, c.venueType)
        ps.setInt(10, c.capacity); ps.setString(11, c.startDate); ps.setString(12, c.endDate)
        ps.setInt(13, c.duration); ps.setString(14, c.platform); ps.setInt(15, c.minPrice)
        ps.setInt(16, c.maxPrice); ps.setInt(17, c.attendance); ps.setString(18, c.ticketStatus)
        ps.addBatch()
        count += 1
        if (count % 500 == 0) { ps.executeBatch(); println(s"    已插入 $count 条...") }
      }
      ps.executeBatch()
      ps.close()
      println(s"  gd_vc.gd_concert 录入完成: ${gdConcerts.size} 条广东省演唱会数据")
    } finally {
      conn.close()
    }
  }

  def saveSingerToMySQL(favConcerts: List[Concert]): Unit = {
    val conn = DriverManager.getConnection(
      "jdbc:mysql://localhost:3306/singer?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true",
      DB_USER, DB_PASS)
    try {
      val createSQL =
        """CREATE TABLE IF NOT EXISTS singer_concert (
          |  id VARCHAR(20) PRIMARY KEY,
          |  title VARCHAR(200), singer VARCHAR(50), popularity INT,
          |  genre VARCHAR(50), province VARCHAR(20), city VARCHAR(20),
          |  venue VARCHAR(100), venue_type VARCHAR(30), capacity INT,
          |  start_date VARCHAR(20), end_date VARCHAR(20), duration INT,
          |  platform VARCHAR(50), min_price INT, max_price INT,
          |  attendance INT, ticket_status VARCHAR(50)
          |) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""".stripMargin
      executeUpdate(conn, createSQL)
      println(s"  singer.singer_concert 表创建/确认成功")

      val insertSQL =
        """INSERT INTO singer_concert (id,title,singer,popularity,genre,province,city,venue,venue_type,capacity,start_date,end_date,duration,platform,min_price,max_price,attendance,ticket_status)
          |VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          |ON DUPLICATE KEY UPDATE title=VALUES(title), attendance=VALUES(attendance)""".stripMargin

      val ps = conn.prepareStatement(insertSQL)
      var count = 0
      favConcerts.foreach { c =>
        ps.setString(1, c.id); ps.setString(2, c.title); ps.setString(3, c.singer)
        ps.setInt(4, c.popularity); ps.setString(5, c.genre); ps.setString(6, c.province)
        ps.setString(7, c.city); ps.setString(8, c.venue); ps.setString(9, c.venueType)
        ps.setInt(10, c.capacity); ps.setString(11, c.startDate); ps.setString(12, c.endDate)
        ps.setInt(13, c.duration); ps.setString(14, c.platform); ps.setInt(15, c.minPrice)
        ps.setInt(16, c.maxPrice); ps.setInt(17, c.attendance); ps.setString(18, c.ticketStatus)
        ps.addBatch()
        count += 1
      }
      ps.executeBatch()
      ps.close()
      println(s"  singer.singer_concert 录入完成: ${favConcerts.size} 条周杰伦演唱会数据")
    } finally {
      conn.close()
    }
  }
}
