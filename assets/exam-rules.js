(function(root, factory){
  var api = factory();
  if(typeof module === 'object' && module.exports) module.exports = api;
  if(root) root.ICTExamRules = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function(){
  'use strict';

  var SUBJECT_MIN_SCORE = 40;
  var AVERAGE_MIN_SCORE = 60;

  function subjectScore(correct, total){
    if(!Number.isFinite(correct) || !Number.isFinite(total) || total <= 0) return 0;
    return correct / total * 100;
  }

  function isSubjectFailed(correct, total){
    return subjectScore(correct, total) < SUBJECT_MIN_SCORE;
  }

  function evaluateScores(scores){
    var valid = (scores || []).filter(Number.isFinite);
    var average = valid.length ? valid.reduce(function(sum, score){ return sum + score; }, 0) / valid.length : 0;
    var failedIndexes = valid.reduce(function(out, score, index){
      if(score < SUBJECT_MIN_SCORE) out.push(index);
      return out;
    }, []);
    return {
      average: average,
      failedIndexes: failedIndexes,
      passed: valid.length > 0 && failedIndexes.length === 0 && average >= AVERAGE_MIN_SCORE
    };
  }

  function evaluateSubjects(subjects){
    var scores = (subjects || []).map(function(subject){
      return subjectScore(subject.correct, subject.total);
    });
    var result = evaluateScores(scores);
    result.scores = scores;
    return result;
  }

  return {
    SUBJECT_MIN_SCORE: SUBJECT_MIN_SCORE,
    AVERAGE_MIN_SCORE: AVERAGE_MIN_SCORE,
    subjectScore: subjectScore,
    isSubjectFailed: isSubjectFailed,
    evaluateScores: evaluateScores,
    evaluateSubjects: evaluateSubjects
  };
});
