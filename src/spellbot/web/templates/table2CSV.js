// modified from source: https://github.com/rubo77/table2CSV
jQuery.fn.table2CSV = function(options) {
  var options = jQuery.extend({
      separator: ',',
      headerSelector: 'th',
      columnSelector: 'td',
      transform_gt_lt: true // make &gt; and &lt; to > and <
    },
    options);

  var csvData = [];
  var el = this;

  //header
  var tmpRow = [];
  $(el).filter(':visible').find(options.headerSelector).each(function() {
    if ($(this).css('display') != 'none') tmpRow[tmpRow.length] = formatData($(this).html());
  });
  row2CSV(tmpRow);

  // actual data
  $(el).find('tr').each(function() {
    var tmpRow = [];
    $(this).filter(':visible').find(options.columnSelector).each(function() {
      var data = $(this).find(".data");
      if (data.length) {
        tmpRow[tmpRow.length] = formatData($(data).html());
      } else if ($(this).css('display') != 'none') {
        tmpRow[tmpRow.length] = formatData($(this).html());
      }
    });
    row2CSV(tmpRow);
  });

  var mydata = csvData.join('\n');
  if (options.transform_gt_lt) {
    mydata = sinri_recover_gt_and_lt(mydata);
  }
  return mydata;

  function sinri_recover_gt_and_lt(input) {
    var regexp = new RegExp(/&gt;/g);
    var input = input.replace(regexp, '>');
    var regexp = new RegExp(/&lt;/g);
    var input = input.replace(regexp, '<');
    return input;
  }

  function row2CSV(tmpRow) {
    var tmp = tmpRow.join('') // to remove any blank rows
    if (tmpRow.length > 0 && tmp != '') {
      var mystr = tmpRow.join(options.separator);
      csvData[csvData.length] = mystr;
    }
  }

  function formatData(input) {
    // double " according to rfc4180
    var regexp = new RegExp(/["]/g);
    var output = input.replace(regexp, '""');
    //HTML
    var regexp = new RegExp(/<[^<]+>/g);
    var output = output.replace(regexp, "");
    output = output.replace(/&nbsp;/gi, ' '); //replace &nbsp;
    if (output == "") return '';
    return '"' + output.trim() + '"';
  }
};
