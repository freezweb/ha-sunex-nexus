pipeline {
    agent { label 'linux' }
    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '15', artifactNumToKeepStr: '10'))
    }
    stages {
        stage('Bootstrap') {
            steps {
                sh '''
                    set -eu
                    python3 scripts/ci_validate.py bootstrap
                '''
            }
        }
        stage('Native HA and protocol tests') {
            steps { sh 'python3 scripts/ci_validate.py tests' }
        }
        stage('Official hassfest') {
            steps { sh 'python3 scripts/ci_validate.py hassfest' }
        }
        stage('Official HACS validator') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'github-https',
                    usernameVariable: 'CI_GITHUB_USER', passwordVariable: 'INPUT_GITHUB_TOKEN')]) {
                    sh '''
                        set +x
                        python3 scripts/ci_validate.py hacs
                    '''
                }
            }
        }
    }
    post {
        always {
            junit allowEmptyResults: true, testResults: '.ci-reports/tests.xml'
            archiveArtifacts allowEmptyArchive: true, artifacts: '.ci-reports/*', fingerprint: true
        }
    }
}
