WITH stats AS (
  SELECT 
    AVG("loss_rate_%") AS avg_loss,
    SQRT(AVG("loss_rate_%" * "loss_rate_%") - AVG("loss_rate_%") * AVG("loss_rate_%")) AS stddev_loss
  FROM veg_loss_rate_df
)
SELECT 
  stats.avg_loss AS average_loss_rate,
  SUM(CASE WHEN v."loss_rate_%" < stats.avg_loss - stats.stddev_loss THEN 1 ELSE 0 END) AS count_below,
  SUM(CASE WHEN v."loss_rate_%" BETWEEN stats.avg_loss - stats.stddev_loss AND stats.avg_loss + stats.stddev_loss THEN 1 ELSE 0 END) AS count_within_one_stddev,
  SUM(CASE WHEN v."loss_rate_%" > stats.avg_loss + stats.stddev_loss THEN 1 ELSE 0 END) AS count_above
FROM veg_loss_rate_df v, stats;