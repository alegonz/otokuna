# otokuna web app

This directory contains the implementation of a web app that allows to browse and
visualize the scrape property data and their daily predictions, meant as a tool 
to aid finding good deals of rental properties.

The web app is made with [Flask](https://flask.palletsprojects.com), 
[Dtale](https://github.com/man-group/dtale) and [Bulma](https://bulma.io), and runs 
on [Gunicorn](https://gunicorn.org) with [Nginx](https://www.nginx.com) as a reverse proxy.

## Running the web app locally

1. Install the dependencies in the [requirements file](../requirements/app.txt).
2. Run the web app with the following command:
    
        ~$ OTOKUNA_CONFIG_FILE=config/config.yml gunicorn app:app
        
3. The app can be accessed from the URL printed in the console.

## Deploying the app
1. Provision an AWS EC2 instance using an Ubuntu AMI.
    1. Create IAM role for to access the S3 bucket where the data is with a read-only policy such as:
            
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": [
                            "s3:ListBucket"
                        ],
                        "Resource": "arn:aws:s3:::mybucket",
                        "Effect": "Allow"
                    },
                    {
                        "Action": [
                            "s3:GetObject"
                        ],
                        "Resource": "arn:aws:s3:::mybucket/*",
                        "Effect": "Allow"
                    }
                ]
            }
            
    2. In the security group, add inbound rules for:
        * SSH (for logging in)
        * HTTP (for the web server)
        * HTTPS (for the web server, optional)
    3. Create key pair for logging over SSH.
    4. Allocate and associate an elastic IP (so that the IP does not change everytime the instance is rebooted).
    
2. (Optional) Register a domain name.
    1. Add records to the hosted zone.
        * Setup the domain’s CNAME record to point to the public DNS of the 
          EC2 instance (e.g. `ec2-12-34-56-78.compute-1.amazonaws.com`).
        * Setup the domain's A record to point to the IP of the EC2 instance
          (e.g. `12.34.56.78`).
    2. (Optional, if HTTPS is desired) Generate a SSL certificate for the domain (using Let's Encrypt).
    
            ~$ sudo snap install core
            ~$ sudo snap refresh core
            ~$ sudo snap install --classic certbot
            ~$ sudo ln -s /snap/bin/certbot /usr/bin/certbot
            ~$ sudo certbot certonly --standalone -d www.example.com

3. Deploy the package (manually).
    1. Generate the debian package (requires the [go-bin-deb](https://github.com/mh-cbon/go-bin-deb) tool).
    
            ~$ make -C debian deb
             
    2. Upload it to the instance.
    3. Install the dependencies.
    
            ~$ sudo apt install python3-venv nginx
            
    3. Install the package and start the service.

            ~$ sudo dpkg -i /path/to/pkg.deb
            ~$ sudo systemctl start otokuna-web-server
            
    3. Enable the site in nginx and restart nginx. 
            
            ~$ sudo ln -s /etc/otokuna-web-server/config/nginx.conf /etc/nginx/sites-enabled/otokuna-app.com
            ~$ sudo systemctl restart nginx
    
    4. (Optional) Setup firewall.
        
            ~$ sudo ufw allow 'Nginx HTTP'
            ~$ sudo ufw allow 'Nginx HTTPS'
            ~$ sudo ufw allow 'OpenSSH'  # so we are not locked out
            ~$ sudo ufw enable
