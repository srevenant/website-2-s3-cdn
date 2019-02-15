pipeline {
  agent { label 'docker-medium' }
  options {
    buildDiscarder(logRotator(numToKeepStr: '5'))
    disableConcurrentBuilds()
    ansiColor('xterm')
  }
  environment {
    SLACK_CHANNEL = "website"
    AWS_ACCESS_KEY_ID = credentials('AWS-AccessKeyId')
    AWS_SECRET_ACCESS_KEY = credentials('AWS-SecretAccessKey')
    WEB_DOMAIN_BUCKET = "your-domain-name-here-that-is-an-s3-bucket"
  }
  stages {
    stage ('Build') {
      steps {
        script {
          sh """
             docker-compose -f docker/deploy/docker-compose.yml build
             """
        }
      }
      post {
        failure {
          slackSend(channel: "${SLACK_CHANNEL}",
                    message: "${env.JOB_NAME} ${env.SLACK_BRANCH} <${env.BUILD_URL}/console|FAILED!>",
                    color: "#C73535")
        }
      }
    }

    stage ('Deploy') {
      steps {
        script {
          sh """
             docker-compose -f docker/deploy/docker-compose.yml run --rm s3push
             """
        }
      }
      post {
        failure {
          slackSend(channel: "${SLACK_CHANNEL}",
                    message: "${env.JOB_NAME} ${env.SLACK_BRANCH} <${env.BUILD_URL}/console|FAILED!>",
                    color: "#C73535")
        }
        success {
          slackSend(channel: "${SLACK_CHANNEL}",
                    message: "${env.JOB_NAME} ${env.SLACK_BRANCH} <${env.BUILD_URL}/console|SUCCESS!>",
                    color: "#11cc00")
        }
      }
    }
  }
}
