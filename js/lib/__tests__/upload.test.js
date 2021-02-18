import { buildUploader, MockUploader, AzureUploader } from '../upload'

describe('buildUploader', () => {
  it('should return a MockUploader if cloudProvider is "mock"', () => {
    const uploader = buildUploader('123', 'file.pdf', {}, 'mock')
    expect(uploader).toBeInstanceOf(MockUploader)
  })

  it('should return an AzureUploader if cloudProvider is "azure"', () => {
    const uploader = buildUploader('123', 'file.pdf', {}, 'azure')
    expect(uploader).toBeInstanceOf(AzureUploader)
  })

  it('should create an AzureUploader with the specified config', () => {
    const uploader = buildUploader(
      '123',
      'file.pdf',
      {
        azureAccountName: 'atat',
        azureContainerName: 'taskorders',
      },
      'azure'
    )
    expect(uploader.accountName).toBe('atat')
    expect(uploader.containerName).toBe('taskorders')
  })
})
