import scala.io.Source

case class Movie(
  title: String,
  rating: Double,
  commentsCount: Int,
  director: String,
  writer: String,
  actors: String,
  genres: String,
  countryRegion: String,
  releaseYear: Int,
  link: String
)

object DoubanAnalysis {

  def main(args: Array[String]): Unit = {
    val movies = loadMovies("douban200.csv")
    println(s"成功加载 ${movies.size} 条电影数据\n")
    task2_count(movies)
    task3_topRating(movies)
    task4_topCommentsAndHighRating(movies)
    task5_average(movies)
    task6_comedyAfter2010(movies)
  }

  def loadMovies(resource: String): List[Movie] = {
    val url = getClass.getClassLoader.getResource(resource)
    if (url == null) { println(s"找不到资源文件: $resource"); return Nil }
    val lines = Source.fromURL(url, "UTF-8").getLines().toList
    if (lines.isEmpty) return Nil
    lines.tail.flatMap(parseLine)
  }

  def parseLine(line: String): Option[Movie] = {
    try {
      val f = parseCSVLine(line)
      if (f.size < 10) return None
      Some(Movie(f(0).trim, f(1).trim.toDouble, f(2).trim.toInt, f(3).trim,
        f(4).trim, f(5).trim, f(6).trim, f(7).trim, f(8).trim.toInt, f(9).trim))
    } catch { case _: Exception => None }
  }

  def parseCSVLine(line: String): List[String] = {
    val result = scala.collection.mutable.ListBuffer[String]()
    val cur = new StringBuilder
    var inQ = false
    for (ch <- line) ch match {
      case '"' => inQ = !inQ
      case ',' if !inQ => result += cur.toString; cur.clear()
      case _ => cur.append(ch)
    }
    result += cur.toString; result.toList
  }

  def task2_count(movies: List[Movie]): Unit = {
    println("=" * 60)
    println("  [2] 电影数量统计")
    println("=" * 60)
    println(s"  豆瓣Top200共有 ${movies.size} 部电影\n")
  }

  def task3_topRating(movies: List[Movie]): Unit = {
    println("=" * 60)
    println("  [3] 评分最高的前5部电影")
    println("=" * 60)
    val top5 = movies.sortBy(-_.rating).take(5)
    top5.zipWithIndex.foreach { case (m, i) =>
      println(s"  ${i + 1}. ${m.title}  评分: ${m.rating}  评分人数: ${m.commentsCount}")
    }
    println("\n  --- 动作电影评分最高的前5部 ---")
    val actionTop5 = movies.filter(_.genres.split("/").contains("动作")).sortBy(-_.rating).take(5)
    actionTop5.zipWithIndex.foreach { case (m, i) =>
      println(s"  ${i + 1}. ${m.title}  评分: ${m.rating}  类型: ${m.genres}")
    }
    println()
  }

  def task4_topCommentsAndHighRating(movies: List[Movie]): Unit = {
    println("=" * 60)
    println("  [4] 评分人数最多的前5部电影")
    println("=" * 60)
    val top5c = movies.sortBy(-_.commentsCount).take(5)
    top5c.zipWithIndex.foreach { case (m, i) =>
      println(s"  ${i + 1}. ${m.title}  评分人数: ${m.commentsCount}  评分: ${m.rating}")
    }
    println("\n  --- 评分高于9分的所有电影 ---")
    val high = movies.filter(_.rating > 9.0).sortBy(-_.rating)
    println(s"  共 ${high.size} 部电影评分高于9.0:")
    high.zipWithIndex.foreach { case (m, i) =>
      println(s"  ${i + 1}. ${m.title}  评分: ${m.rating}  评分人数: ${m.commentsCount}")
    }
    println()
  }

  def task5_average(movies: List[Movie]): Unit = {
    println("=" * 60)
    println("  [5] 200部电影的平均评分和平均评分人数")
    println("=" * 60)
    val avgR = movies.map(_.rating).sum / movies.size
    val avgC = movies.map(_.commentsCount).sum.toDouble / movies.size
    println(f"  平均评分:   $avgR%.2f")
    println(f"  平均评分人数: ${avgC}%.0f\n")
  }

  def task6_comedyAfter2010(movies: List[Movie]): Unit = {
    println("=" * 60)
    println("  [6] 2010年后拍的所有喜剧电影")
    println("=" * 60)
    val comedies = movies.filter(m =>
      m.releaseYear > 2010 && m.genres.split("/").contains("喜剧")
    ).sortBy(-_.rating)
    println(s"  共 ${comedies.size} 部:")
    comedies.zipWithIndex.foreach { case (m, i) =>
      println(s"  ${i + 1}. ${m.title}  评分: ${m.rating}  年份: ${m.releaseYear}  类型: ${m.genres}")
    }
    println()
  }
}
